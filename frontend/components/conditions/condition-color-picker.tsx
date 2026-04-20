"use client";

import { Input } from "@/components/ui/input";
import { TAKEOFF_CONDITION_COLORS } from "@/lib/takeoff-condition-colors";
import { cn } from "@/lib/utils";

interface ConditionColorPickerProps {
  value: string;
  onChange: (hex: string) => void;
  disabled?: boolean;
}

export function ConditionColorPicker({
  value,
  onChange,
  disabled,
}: ConditionColorPickerProps) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {TAKEOFF_CONDITION_COLORS.map(({ name, hex }) => (
          <button
            key={hex}
            type="button"
            disabled={disabled}
            title={name}
            onClick={() => onChange(hex)}
            className={cn(
              "h-7 w-7 rounded-sm border-2 transition-transform hover:scale-105",
              value.toLowerCase() === hex.toLowerCase()
                ? "border-primary ring-1 ring-primary/40"
                : "border-border hover:border-border-hover"
            )}
            style={{ backgroundColor: hex }}
          />
        ))}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Hex
        </span>
        <Input
          className="h-8 max-w-[120px] font-mono text-xs"
          value={value}
          disabled={disabled}
          onChange={(e) => {
            const v = e.target.value.trim();
            if (v.length <= 7) onChange(v);
          }}
          placeholder="#RRGGBB"
          spellCheck={false}
        />
      </div>
    </div>
  );
}
