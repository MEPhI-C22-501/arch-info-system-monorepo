export type CapacitySnapshot = { userId: string; plannedHours: number; actualHours: number; availableHours: number };

export function compareAssignee(baseline: CapacitySnapshot, current?: CapacitySnapshot) {
  const planned = Number(baseline.plannedHours || 0);
  const actual = Number(current?.actualHours || 0);
  return {
    planned,
    currentPlan: Number(current?.plannedHours || 0),
    actual,
    deviation: actual - planned,
    available: Number(baseline.availableHours || 0),
  };
}
