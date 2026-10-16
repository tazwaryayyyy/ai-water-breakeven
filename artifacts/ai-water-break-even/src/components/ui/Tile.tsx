import { type HTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface TileProps extends HTMLAttributes<HTMLElement> {
  /** Swiss-style section index, e.g. "01". */
  index?: string;
  title: string;
  note?: string;
  /** Right-aligned slot in the tile header (selectors, legends). */
  actions?: ReactNode;
  footer?: React.ReactNode;
  dense?: boolean;
}

/**
 * One bento cell: hairline border, index + small-caps kicker, generous
 * interior. Sharp corners — the grid itself is the ornament.
 */
export function Tile({
  index,
  title,
  note,
  actions,
  footer,
  dense = false,
  className,
  children,
  ...props
}: TileProps) {
  return (
    <section
      className={cn(
        'flex min-w-0 flex-col border border-line bg-surface',
        'shadow-[0_1px_0_0_rgba(33,28,21,0.04)]',
        className,
      )}
      {...props}
    >
      <header className="flex items-start justify-between gap-4 border-b border-line px-5 pt-4 pb-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2.5">
            {index && (
              <span className="font-sans text-[10px] font-semibold tracking-[0.14em] text-muted">
                {index}
              </span>
            )}
            <h2 className="font-sans text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              {title}
            </h2>
          </div>
          {note && <p className="mt-1 text-[12px] leading-snug text-ink-soft">{note}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </header>
      <div className={cn('min-w-0 flex-1', dense ? 'p-3' : 'p-5')}>{children}</div>
      {footer && (
        <footer className="border-t border-line px-5 py-3 text-[11px] leading-relaxed text-muted">
          {footer}
        </footer>
      )}
    </section>
  );
}
