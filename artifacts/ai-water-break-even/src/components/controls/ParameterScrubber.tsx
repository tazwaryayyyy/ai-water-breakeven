import { type CSSProperties } from 'react';
import { formatInt } from '@/lib/format';
import { PARAMETER_LABELS, PARAMETER_LIMITS, type ParameterKey } from '@/domain/model/types';

export interface ParameterSpec {
  key: ParameterKey;
  label: string;
  hint: string;
  unit: string;
  display: (value: number) => string;
}

/** Display metadata for the eight model parameters. */
export const PARAMETER_SPECS: ParameterSpec[] = [
  {
    key: 'startingWaterUse',
    label: PARAMETER_LABELS.startingWaterUse,
    hint: 'Annual operational water burden at year zero',
    unit: 'M m³/yr',
    display: (v) => `${formatInt(v)} M m³`,
  },
  {
    key: 'aiGrowthRate',
    label: PARAMETER_LABELS.aiGrowthRate,
    hint: 'Annual increase in simulated AI water demand',
    unit: '%/yr',
    display: (v) => `${(v * 100).toFixed(1)}%/yr`,
  },
  {
    key: 'efficiencyImprovement',
    label: PARAMETER_LABELS.efficiencyImprovement,
    hint: 'Annual reduction in AI water intensity',
    unit: '%/yr',
    display: (v) => `${(v * 100).toFixed(1)}%/yr`,
  },
  {
    key: 'savingsPotential',
    label: PARAMETER_LABELS.savingsPotential,
    hint: 'Annual water that interventions could save before realization',
    unit: 'M m³/yr',
    display: (v) => `${formatInt(v)} M m³`,
  },
  {
    key: 'interventionEffectiveness',
    label: PARAMETER_LABELS.interventionEffectiveness,
    hint: 'Share of adopted interventions that deliver savings',
    unit: '%',
    display: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: 'adoptionRate',
    label: PARAMETER_LABELS.adoptionRate,
    hint: 'Long-run share of water-saving interventions in use',
    unit: '%',
    display: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: 'realizationFactor',
    label: PARAMETER_LABELS.realizationFactor,
    hint: 'Share of theoretical savings that become real',
    unit: '%',
    display: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: 'attributionFraction',
    label: PARAMETER_LABELS.attributionFraction,
    hint: 'Share of realized savings credited to AI-enabled action',
    unit: '%',
    display: (v) => `${Math.round(v * 100)}%`,
  },
];

interface ParameterScrubberProps {
  label: string;
  hint?: string;
  unit?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display?: (value: number) => string;
  onChange: (value: number) => void;
  testId?: string;
}

/**
 * Precision slider with tactile feedback: filled track to the thumb,
 * endpoint scales, and a live tabular-numeral readout. The native range
 * input keeps full keyboard and assistive-tech behaviour for free.
 */
export function ParameterScrubber({
  label,
  hint,
  unit,
  value,
  min,
  max,
  step,
  display,
  onChange,
  testId,
}: ParameterScrubberProps) {
  const fill = max > min ? ((value - min) / (max - min)) * 100 : 0;
  const shown = display ? display(value) : String(value);

  return (
    <div className="group">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={testId} className="text-[11px] font-semibold text-ink">
          {label}
        </label>
        <span className="flex items-baseline gap-1.5">
          <span className="font-display text-[15px] leading-none text-ink tabular-nums transition-transform duration-75 origin-right group-hover:scale-[1.04]">
            {shown}
          </span>
          {unit && <span className="text-[9px] uppercase tracking-[0.1em] text-muted">{unit}</span>}
        </span>
      </div>
      <input
        id={testId}
        data-testid={testId}
        aria-label={label}
        type="range"
        inputMode="decimal"
        className="scrubber mt-2.5 w-full"
        style={{ '--fill': `${fill}%` } as CSSProperties}
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className="mt-1 flex justify-between text-[9.5px] text-muted tabular-nums">
        <span>{display ? display(min) : min}</span>
        <span>{display ? display(max) : max}</span>
      </div>
      {hint && <p className="mt-1 text-[10.5px] leading-snug text-muted">{hint}</p>}
    </div>
  );
}
