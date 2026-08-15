import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface FieldDarkProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

/**
 * Input styled for the dark auth card background (app/(auth)/layout.tsx).
 * Kept separate from components/ui/field.tsx, which targets the light
 * dashboard surface — sharing one component and overriding colors via
 * props would be more indirection than two small, honest components.
 */
export const FieldDark = forwardRef<HTMLInputElement, FieldDarkProps>(function FieldDark(
  { label, id, className, ...props },
  ref
) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-ink-300">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        className={cn(
          "rounded-md border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-white",
          "placeholder:text-ink-500",
          "focus:border-ink-400",
          className
        )}
        {...props}
      />
    </div>
  );
});
