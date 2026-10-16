import { type ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'solid' | 'outline' | 'ghost';
type Size = 'sm' | 'md';

const VARIANTS: Record<Variant, string> = {
  solid: 'bg-ink text-paper border-ink hover:bg-ink/88',
  outline: 'bg-transparent text-ink border-line hover:border-ink/50 hover:bg-ink/[0.03]',
  ghost: 'bg-transparent text-ink-soft border-transparent hover:text-ink hover:bg-ink/[0.05]',
};

const SIZES: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-[11px] tracking-[0.08em]',
  md: 'h-9 px-4 text-xs tracking-[0.08em]',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

/** Minimal Swiss-editorial button: uppercase micro-label, hairline border. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'outline', size = 'md', type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex items-center gap-1.5 border font-sans font-medium uppercase',
        'transition-colors duration-100 cursor-pointer',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal',
        'disabled:pointer-events-none disabled:opacity-40',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  );
});
