import { cn } from "@/lib/utils";
import { forwardRef, type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", ...props },
  ref
) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-ink-900 text-white hover:bg-ink-800",
        variant === "secondary" &&
          "border border-ink-200 bg-white text-ink-800 hover:bg-ink-50",
        variant === "ghost" && "text-ink-600 hover:bg-ink-100",
        className
      )}
      {...props}
    />
  );
});
