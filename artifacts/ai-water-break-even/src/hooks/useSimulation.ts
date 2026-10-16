/**
 * React 19 hook that owns the simulation lifecycle: config state, a
 * debounced dispatch to the worker (so 60 FPS slider drags coalesce into
 * one run each), staged progress, and stale-result rejection.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { sanitizeConfig, SCENARIO_PRESETS, type ScenarioPreset } from '@/domain/model/simulation-engine';
import {
  DEFAULT_CONFIG,
  type ParameterKey,
  type RunControlKey,
  type ScenarioConfig,
  type SensitivityMetric,
  type SimulationResult,
} from '@/domain/model/types';
import {
  getSimulationClient,
  RequestCancelledError,
  type SimulationProgress,
} from '@/domain/worker/worker-client';

/** Coalesce slider activity: one worker dispatch per pause in dragging. */
const DISPATCH_DEBOUNCE_MS = 130;

const STAGE_OFFSETS: Record<SimulationProgress['stage'], number> = {
  baseline: 0,
  sensitivity: 0.6,
  scenarios: 0.85,
};
const STAGE_WEIGHTS: Record<SimulationProgress['stage'], number> = {
  baseline: 0.6,
  sensitivity: 0.25,
  scenarios: 0.15,
};

export interface ComputingState {
  isComputing: boolean;
  /** Overall fraction in [0, 1] across all stages; null when idle. */
  fraction: number | null;
  stage: SimulationProgress['stage'] | null;
}

export function useSimulation() {
  const [config, setConfig] = useState<ScenarioConfig>(DEFAULT_CONFIG);
  const [sensitivityMetric, setSensitivityMetric] = useState<SensitivityMetric>('finalBalance');
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [computing, setComputing] = useState<ComputingState>({
    isComputing: true,
    fraction: null,
    stage: null,
  });
  /** Generation counter so a slow run can never clobber a newer result. */
  const dispatchGeneration = useRef(0);

  useEffect(() => {
    const client = getSimulationClient();
    const generation = ++dispatchGeneration.current;
    let timer: ReturnType<typeof setTimeout> | undefined;

    setComputing((state) => ({ ...state, isComputing: true }));
    timer = setTimeout(() => {
      client
        .execute(sanitizeConfig(config), {
          includeSensitivity: true,
          includeScenarios: true,
          sensitivityMetric,
          onProgress: (progress) => {
            if (dispatchGeneration.current !== generation) return;
            setComputing({
              isComputing: true,
              stage: progress.stage,
              fraction:
                STAGE_OFFSETS[progress.stage] +
                STAGE_WEIGHTS[progress.stage] *
                  (progress.total > 0 ? progress.completed / progress.total : 1),
            });
          },
        })
        .then((next) => {
          if (dispatchGeneration.current !== generation) return;
          setResult(next);
          setError(null);
          setComputing({ isComputing: false, fraction: null, stage: null });
        })
        .catch((cause: unknown) => {
          if (dispatchGeneration.current !== generation) return;
          if (cause instanceof RequestCancelledError) return;
          setError(cause instanceof Error ? cause.message : 'The simulation could not complete.');
          setComputing({ isComputing: false, fraction: null, stage: null });
        });
    }, DISPATCH_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      client.cancelPending();
    };
  }, [config, sensitivityMetric]);

  const updateParameter = useCallback(
    (key: ParameterKey | RunControlKey, value: number) => {
      setConfig((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const applyPreset = useCallback((preset: ScenarioPreset) => {
    setConfig((current) => ({ ...current, ...preset.values }));
  }, []);

  const reset = useCallback(() => setConfig(DEFAULT_CONFIG), []);

  const newSeed = useCallback(() => {
    setConfig((current) => ({
      ...current,
      seed: (Math.floor(Math.random() * 999_999_998) + 1),
    }));
  }, []);

  const activePreset = useMemo(() => {
    for (const preset of SCENARIO_PRESETS) {
      const entries = Object.entries(preset.values) as Array<[ParameterKey, number]>;
      if (entries.every(([key, value]) => currentMatches(config, key, value))) return preset;
    }
    return null;
  }, [config]);

  return {
    config,
    setConfig,
    result,
    error,
    computing,
    sensitivityMetric,
    activePreset,
    setSensitivityMetric,
    updateParameter,
    applyPreset,
    reset,
    newSeed,
  };
}

function currentMatches(config: ScenarioConfig, key: ParameterKey, value: number): boolean {
  return Math.abs(config[key] - value) < 1e-9;
}
