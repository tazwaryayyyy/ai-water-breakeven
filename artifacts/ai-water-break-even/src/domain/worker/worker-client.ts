/**
 * Typed, framework-free bridge to the simulation worker.
 *
 * A lazily-created singleton native Worker (no Comlink, no RPC library):
 * requests carry incrementing ids, progress events are routed back to the
 * originating call, and issuing a new request supersedes any in-flight one
 * — the client rejects the stale promise and the worker aborts its chunked
 * pass at the next yield point via the generation token.
 */

import { unpackQuantiles } from '../model/simulation-engine';
import { SCENARIO_DEFINITIONS } from '../model/simulation-engine';
import type {
  ResultPayload,
  ScenarioConfig,
  SensitivityMetric,
  SimulationResult,
  WorkerOutboundMessage,
  WorkerStage,
} from '../model/types';

export class RequestCancelledError extends Error {
  constructor(message = 'Simulation request was superseded or cancelled') {
    super(message);
    this.name = 'RequestCancelledError';
  }
}

export interface SimulationProgress {
  stage: WorkerStage;
  completed: number;
  total: number;
}

export interface ExecuteOptions {
  includeSensitivity?: boolean;
  includeScenarios?: boolean;
  sensitivityMetric?: SensitivityMetric;
  onProgress?: (progress: SimulationProgress) => void;
}

interface PendingRequest {
  resolve: (result: SimulationResult) => void;
  reject: (error: Error) => void;
  onProgress?: (progress: SimulationProgress) => void;
}

/** Decode the transferred wire payload into the UI-facing result. */
function decodeResult(payload: ResultPayload): SimulationResult {
  const { summary, config } = payload;
  const horizon = summary.years.length;
  const simulations = config.simulations;
  const scenarioDescription = new Map(
    SCENARIO_DEFINITIONS.map((definition) => [definition.name, definition.description] as const),
  );
  return {
    summary: {
      config,
      years: Array.from(summary.years),
      burden: unpackQuantiles(summary.burdenQuantiles, horizon),
      savings: unpackQuantiles(summary.savingsQuantiles, horizon),
      balance: unpackQuantiles(summary.balanceQuantiles, horizon),
      breakEvenCounts: Array.from(summary.breakEvenYearCounts),
      neverCount: summary.neverCount,
      probabilities: summary.probabilities,
      neverProbability: summary.neverCount / simulations,
      medianBreakEvenYear: summary.medianBreakEvenYear,
      finalMedianBalance: summary.finalMedianBalance,
      finalMedianBurden: summary.finalMedianBurden,
      finalMedianSavings: summary.finalMedianSavings,
    },
    sensitivity: payload.sensitivity,
    scenarios: payload.scenarioOutcomes.map((outcome) => ({
      ...outcome,
      medianBalance: Array.from(outcome.medianBalance),
      description: scenarioDescription.get(outcome.name) ?? '',
    })),
    computeMs: payload.computeMs,
  };
}

export class SimulationWorkerClient {
  private worker: Worker | null = null;
  private nextRequestId = 0;
  private readonly pending = new Map<number, PendingRequest>();
  private lastRequestId = 0;

  /** Issue a run; supersedes and cancels any request still in flight. */
  public execute(config: ScenarioConfig, options: ExecuteOptions = {}): Promise<SimulationResult> {
    this.cancelPending();
    const requestId = ++this.nextRequestId;
    this.lastRequestId = requestId;

    return new Promise<SimulationResult>((resolve, reject) => {
      this.pending.set(requestId, { resolve, reject, onProgress: options.onProgress });
      this.ensureWorker().postMessage({
        type: 'run',
        requestId,
        config,
        includeSensitivity: options.includeSensitivity ?? true,
        includeScenarios: options.includeScenarios ?? true,
        sensitivityMetric: options.sensitivityMetric ?? 'finalBalance',
      });
    });
  }

  /** Reject every in-flight request and tell the worker to stop computing. */
  public cancelPending(): void {
    if (this.pending.size > 0) {
      for (const entry of this.pending.values()) {
        entry.reject(new RequestCancelledError());
      }
      this.pending.clear();
    }
    if (this.worker && this.lastRequestId > 0) {
      this.worker.postMessage({ type: 'cancel', requestId: this.lastRequestId });
    }
  }

  public dispose(): void {
    this.cancelPending();
    this.worker?.terminate();
    this.worker = null;
  }

  private ensureWorker(): Worker {
    if (!this.worker) {
      this.worker = new Worker(new URL('./simulation.worker.ts', import.meta.url), {
        type: 'module',
      });
      this.worker.onmessage = (event: MessageEvent<WorkerOutboundMessage>) => {
        this.handleMessage(event.data);
      };
      this.worker.onerror = (event: ErrorEvent) => {
        const error = new Error(event.message || 'Simulation worker failed');
        for (const entry of this.pending.values()) entry.reject(error);
        this.pending.clear();
      };
    }
    return this.worker;
  }

  private handleMessage(message: WorkerOutboundMessage): void {
    const entry = this.pending.get(message.requestId);
    if (!entry) return; // Stale event for an already-cancelled request.
    switch (message.type) {
      case 'progress':
        entry.onProgress?.({
          stage: message.stage,
          completed: message.completed,
          total: message.total,
        });
        break;
      case 'result':
        this.pending.delete(message.requestId);
        entry.resolve(decodeResult(message.payload));
        break;
      case 'error':
        this.pending.delete(message.requestId);
        entry.reject(new Error(message.message));
        break;
    }
  }
}

let singleton: SimulationWorkerClient | null = null;

/** Process-wide simulation client. Created on first use, browser only. */
export function getSimulationClient(): SimulationWorkerClient {
  if (!singleton) singleton = new SimulationWorkerClient();
  return singleton;
}
