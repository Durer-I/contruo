import { formatAreaQuantity } from "@/lib/area-geometry";
import { formatLength } from "@/lib/linear-geometry";
import type { ConditionInfo } from "@/types/condition";
import type { MeasurementInfo } from "@/types/measurement";

export function effectiveQuantity(m: MeasurementInfo): number {
  return m.override_value != null ? m.override_value : m.measured_value;
}

/** Display primary quantity for a measurement using the condition's unit conventions. */
export function formatEffectiveQuantity(
  m: MeasurementInfo,
  condition: ConditionInfo,
  sheetScaleUnit: string | null | undefined
): string {
  const v = effectiveQuantity(m);
  if (condition.measurement_type === "count") {
    return Math.round(v).toLocaleString();
  }
  if (condition.measurement_type === "area") {
    return formatAreaQuantity(v, condition.unit);
  }
  return formatLength(v, sheetScaleUnit, condition.unit);
}

export function sumEffectiveQuantities(
  measurements: MeasurementInfo[],
  condition: ConditionInfo
): number {
  let t = 0;
  for (const m of measurements) {
    if (m.condition_id !== condition.id) continue;
    t += effectiveQuantity(m);
  }
  return t;
}
