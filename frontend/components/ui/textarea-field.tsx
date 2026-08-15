import { cn } from "@/lib/utils";
import { forwardRef, type TextareaHTMLAttributes } from "react";

interface TextareaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export const TextareaField = forwardRef<HTMLTextAreaElement, TextareaFieldProps>(
  function TextareaField({ label, error, id, className, ...props }, ref) {
    const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium text-ink-700">
          {label}
        </label>
        <textarea
          ref={ref}
          id={inputId}
          rows={4}
          className={cn(
            "resize-none rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900",
            "placeholder:text-ink-400",
            "focus:border-ink-500",
            error && "border-signal",
            className
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="text-sm text-signal">
            {error}
          </p>
        )}
      </div>
    );
  }
);
