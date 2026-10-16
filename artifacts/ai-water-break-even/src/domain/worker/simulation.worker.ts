/**
 * Dedicated simulation worker. All Monte Carlo passes — baseline,
 * sensitivity probes, and scenario comparison — run here so the main
 * thread never blocks.
 *
 * Cancellation is an event-based generation token: every 'run' message
 * bumps `activeRequestId`; long computations chunk their work and yield to
 * the message loop between chunks, aborting as soon as their token is no
 * longer current. A new run therefore supersedes an in-flight run within
 * one chunk (~2500 paths), with no shared state to corrupt.
 */

import { FastPRNG } from '../math/prng';
import {
  SIMULATION_CHUNK,
  allocateExtraction,
  allocateMatrices,
  runScenarioPass,
  runSensitivityPass,
  sanitizeConfig,
  simulateChunk,
  summarizeMatrices,
} from '../model/simulation-engine';
import type { RunRequestMessage, WorkerInboundMessage, WorkerOutboundMessage } from '../model/types';

interface WorkerScope {
  postMessage(message: WorkerOutboundMessage, transfer?: Transferable[]): void;
  addEventListener(
    type: 'message',
    listener: (event: MessageEvent<WorkerInboundMessage>) => void,
  ): void;
}

const scope = self as unknown as WorkerScope;

/** Token of the run that currently owns the worker; 0 means idle/cancelled. */
let activeRequestId = 0;

/** Hand control back to the message loop so queued messages can run. */
const yieldToMessages = (): Promise<void> =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });

scope.addEventListener('message', (event: MessageEvent<WorkerInboundMessage>) => {
  const message = event.data;
  if (message.type === 'run') {
    activeRequestId = message.requestId;
    void handleRun(message);
  } else if (message.type === 'cancel' && message.requestId === activeRequestId) {
    activeRequestId = 0;
  }
});

async function handleRun(request: RunRequestMessage): Promise<void> {
  const requestId = request.requestId;
  const isStale = (): boolean => activeRequestId !== requestId;
  const started = performance.now();

  const post = (message: WorkerOutboundMessage, transfer?: Transferable[]): void => {
    scope.postMessage(message, transfer);
  };

  try {
    const config = sanitizeConfig(request.config);

    /* ---------------------------- Baseline pass ---------------------------- */
    const matrices = allocateMatrices(config.simulations, config.horizon);
    const buffers = allocateExtraction(config.simulations, config.horizon);
    const rng = new FastPRNG(config.seed);

    for (let from = 0; from < config.simulations; from += SIMULATION_CHUNK) {
      if (isStale()) return;
      const to = Math.min(from + SIMULATION_CHUNK, config.simulations);
      simulateChunk(config, matrices, rng, from, to);
      post({
        type: 'progress',
        requestId,
        stage: 'baseline',
        completed: to,
        total: config.simulations,
      });
      await yieldToMessages();
    }
    if (isStale()) return;

    const summary = summarizeMatrices(matrices, config, buffers);

    /* -------------------------- Sensitivity pass --------------------------- */
    let sensitivity: ReturnType<typeof runSensitivityPass>['results'] = [];
    if (request.includeSensitivity) {
      post({ type: 'progress', requestId, stage: 'sensitivity', completed: 0, total: 8 });
      await yieldToMessages();
      if (isStale()) return;
      sensitivity = runSensitivityPass(config, request.sensitivityMetric).results;
      post({ type: 'progress', requestId, stage: 'sensitivity', completed: 8, total: 8 });
    }
    if (isStale()) return;

    /* --------------------------- Scenario pass ----------------------------- */
    let scenarioOutcomes: ReturnType<typeof runScenarioPass> = [];
    if (request.includeScenarios) {
      post({ type: 'progress', requestId, stage: 'scenarios', completed: 0, total: 3 });
      await yieldToMessages();
      if (isStale()) return;
      scenarioOutcomes = runScenarioPass(config);
      post({ type: 'progress', requestId, stage: 'scenarios', completed: 3, total: 3 });
    }
    if (isStale()) return;

    const payload = {
      config,
      summary,
      sensitivity,
      scenarioOutcomes,
      computeMs: performance.now() - started,
    };
    const transfer: Transferable[] = [
      summary.years.buffer,
      summary.burdenQuantiles.buffer,
      summary.savingsQuantiles.buffer,
      summary.balanceQuantiles.buffer,
      summary.breakEvenYearCounts.buffer,
      ...scenarioOutcomes.map((outcome) => outcome.medianBalance.buffer),
    ];
    post({ type: 'result', requestId, payload }, transfer);
  } catch (error) {
    if (!isStale()) {
      post({
        type: 'error',
        requestId,
        message: error instanceof Error ? error.message : 'Simulation failed',
      });
    }
  }
}
