/**
 * CSV / JSON / high-DPI PNG export for the current ensemble.
 *
 * CSV carries every quantile of all three curves plus the break-even
 * distribution; JSON snapshots the full model state for reproducibility;
 * PNG re-renders the main chart SVG onto an offscreen canvas at 3× scale.
 */

import { useCallback } from 'react';
import type { SimulationResult } from '@/domain/model/types';

const PNG_SCALE = 3;

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function buildCSV(result: SimulationResult): string {
  const { summary } = result;
  const { years, burden, savings, balance, breakEvenCounts, config } = summary;
  const lines: string[] = [];

  lines.push('# AI water break-even — Monte Carlo ensemble');
  lines.push(
    `# simulations=${config.simulations} horizon=${config.horizon} seed=${config.seed} volumes in million m3`,
  );
  lines.push('');
  lines.push(
    [
      'year',
      'burden_p5',
      'burden_p25',
      'burden_median',
      'burden_p75',
      'burden_p95',
      'savings_p5',
      'savings_p25',
      'savings_median',
      'savings_p75',
      'savings_p95',
      'balance_p5',
      'balance_p25',
      'balance_median',
      'balance_p75',
      'balance_p95',
    ].join(','),
  );
  for (let i = 0; i < years.length; i++) {
    lines.push(
      [
        years[i],
        burden.p5[i],
        burden.p25[i],
        burden.median[i],
        burden.p75[i],
        burden.p95[i],
        savings.p5[i],
        savings.p25[i],
        savings.median[i],
        savings.p75[i],
        savings.p95[i],
        balance.p5[i],
        balance.p25[i],
        balance.median[i],
        balance.p75[i],
        balance.p95[i],
      ].join(','),
    );
  }

  lines.push('');
  lines.push('# sustained break-even year, path count');
  for (let year = 1; year <= breakEvenCounts.length; year++) {
    const count = breakEvenCounts[year - 1];
    if (count > 0) lines.push(`${year},${count}`);
  }
  lines.push(`never,${summary.neverCount}`);
  lines.push('');
  lines.push('# scenario comparison (median balance, million m3)');
  lines.push(['scenario', ...years].join(','));
  for (const scenario of result.scenarios) {
    lines.push([scenario.name, ...scenario.medianBalance].join(','));
  }
  return lines.join('\n');
}

export function useExport(result: SimulationResult | null) {
  const exportCSV = useCallback(() => {
    if (!result) return;
    downloadBlob(
      new Blob([buildCSV(result)], { type: 'text/csv;charset=utf-8' }),
      'ai-water-break-even-ensemble.csv',
    );
  }, [result]);

  const exportJSON = useCallback(() => {
    if (!result) return;
    const payload = {
      generatedAt: new Date().toISOString(),
      engine: {
        prng: 'xoshiro128** (SplitMix32 seeded, Math.imul, no BigInt)',
        sustainedBreakEven: 'backwards scan for last negative year',
        quantiles: 'in-place Float64Array sort, Hyndman-Fan type 7',
      },
      config: result.summary.config,
      summary: result.summary,
      sensitivity: result.sensitivity,
      scenarios: result.scenarios,
      computeMs: result.computeMs,
    };
    downloadBlob(
      new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }),
      'ai-water-break-even-simulation.json',
    );
  }, [result]);

  const exportPNG = useCallback(
    (selector: string, filename = 'ai-water-break-even-chart.png') => {
      const svg = document.querySelector<SVGSVGElement>(`${selector} svg`);
      if (!svg) return;
      const width = svg.clientWidth || 1200;
      const height = svg.clientHeight || 640;
      const clone = svg.cloneNode(true) as SVGSVGElement;
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clone.setAttribute('width', String(width));
      clone.setAttribute('height', String(height));
      const serialized = new XMLSerializer().serializeToString(clone);
      const svgUrl = URL.createObjectURL(
        new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' }),
      );
      const image = new Image();
      image.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = width * PNG_SCALE;
        canvas.height = height * PNG_SCALE;
        const context = canvas.getContext('2d');
        if (context) {
          context.scale(PNG_SCALE, PNG_SCALE);
          context.fillStyle = '#fffdf7';
          context.fillRect(0, 0, width, height);
          context.drawImage(image, 0, 0, width, height);
          canvas.toBlob((blob) => {
            if (blob) downloadBlob(blob, filename);
          }, 'image/png');
        }
        URL.revokeObjectURL(svgUrl);
      };
      image.onerror = () => URL.revokeObjectURL(svgUrl);
      image.src = svgUrl;
    },
    [],
  );

  return { exportCSV, exportJSON, exportPNG };
}
