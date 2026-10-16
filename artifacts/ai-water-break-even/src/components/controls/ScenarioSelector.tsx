import { RotateCcw, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { ScenarioPreset } from '@/domain/model/simulation-engine';

interface ScenarioSelectorProps {
  presets: ScenarioPreset[];
  activePreset: ScenarioPreset | null;
  onSelect: (preset: ScenarioPreset) => void;
  onReset: () => void;
  onNewSeed: () => void;
}

/**
 * One-click preset scenarios. Selecting a preset writes its eight parameter
 * values into the controls (run controls — horizon, paths, seed — stay as
 * the user set them) and the debounced worker dispatch picks up the change.
 */
export function ScenarioSelector({
  presets,
  activePreset,
  onSelect,
  onReset,
  onNewSeed,
}: ScenarioSelectorProps) {
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {presets.map((preset) => {
          const active = activePreset?.id === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              data-testid={`button-preset-${preset.id}`}
              aria-pressed={active}
              onClick={() => onSelect(preset)}
              className={
                'cursor-pointer border p-2.5 text-left transition-colors duration-100 ' +
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ' +
                (active
                  ? 'border-teal bg-teal/[0.07]'
                  : 'border-line bg-surface hover:border-ink/40 hover:bg-ink/[0.02]')
              }
            >
              <span
                className={
                  'block text-[11px] font-semibold leading-tight ' +
                  (active ? 'text-teal' : 'text-ink')
                }
              >
                {preset.name}
              </span>
              <span className="mt-1 block text-[10px] leading-snug text-muted">{preset.note}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className="text-[10.5px] text-muted">
          {activePreset ? `Loaded: ${activePreset.name}` : 'Custom assumptions'}
        </span>
        <div className="flex gap-1.5">
          <Button size="sm" variant="ghost" onClick={onReset}>
            <RotateCcw size={12} /> Reset
          </Button>
          <Button size="sm" variant="ghost" onClick={onNewSeed}>
            <Sparkles size={12} /> New seed
          </Button>
        </div>
      </div>
    </div>
  );
}
