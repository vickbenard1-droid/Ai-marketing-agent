import { cn } from "@/lib/utils";

interface ChipOption {
  value: string;
  label: string;
}

interface ChipMultiSelectProps {
  label: string;
  options: ChipOption[];
  selected: string[];
  onChange: (next: string[]) => void;
}

export function ChipMultiSelect({ label, options, selected, onChange }: ChipMultiSelectProps) {
  function toggle(value: string) {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-ink-700">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => toggle(option.value)}
              aria-pressed={isSelected}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
                isSelected
                  ? "border-ink-900 bg-ink-900 text-white"
                  : "border-ink-200 bg-white text-ink-700 hover:border-ink-400"
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
