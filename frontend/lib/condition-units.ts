import type { ConditionInfo, MeasurementType } from "@/types/condition";

/** Takeoff tools that imply a condition measurement type for picking & shortcuts. */
export type TakeoffToolForConditionFilter = "select" | "linear" | "area" | "count" | "scale";

/** Conditions compatible with the active takeoff tool (for toolbar menu and 1–9 shortcuts). */
export function conditionsMatchingTakeoffTool(
  conditions: ConditionInfo[],
  tool: TakeoffToolForConditionFilter
): ConditionInfo[] {
  if (tool === "linear") return conditions.filter((c) => c.measurement_type === "linear");
  if (tool === "area") return conditions.filter((c) => c.measurement_type === "area");
  if (tool === "count") return conditions.filter((c) => c.measurement_type === "count");
  return conditions;
}

/** Primary units offered in the UI for each measurement type (matches backend quantity helpers). */
export const UNITS_BY_MEASUREMENT_TYPE: Record<MeasurementType, readonly string[]> = {
  linear: ["LF", "FT", "m", "LS"],
  area: ["SF", "SY", "m²"],
  count: ["EA"],
};

export function unitsForMeasurementType(mt: MeasurementType): readonly string[] {
  return UNITS_BY_MEASUREMENT_TYPE[mt];
}

/** Default unit when picking a type (new condition or after type change). */
export function defaultUnitForMeasurementType(mt: MeasurementType): string {
  const u = UNITS_BY_MEASUREMENT_TYPE[mt];
  return u[0] ?? "EA";
}
