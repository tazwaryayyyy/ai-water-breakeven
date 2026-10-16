import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * Responsive editorial grid: single column on phones, six columns on
 * tablets, twelve on large displays. Tiles claim spans via Tailwind
 * col-span utilities passed from their composition site.
 */
export function BentoGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-4 md:grid-cols-6 xl:grid-cols-12',
        className,
      )}
    >
      {children}
    </div>
  );
}
