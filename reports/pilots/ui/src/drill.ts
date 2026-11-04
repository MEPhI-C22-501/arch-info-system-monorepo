import type { ReportQuery } from './types';

export interface DrillStep { slice: string; id: string | null }

// Week and month are two views of the same time axis: after one of them the other adds nothing.
const SAME_AXIS: Record<string, string> = { week: 'month', month: 'week' };

/** Next level of SCR-03: the report's next slice after the deepest one used; 'record' is the last level. */
export function nextSlice(slices: string[], used: string[]): string | null {
  const blocked = new Set(used.flatMap((s) => [s, SAME_AXIS[s]].filter(Boolean)));
  const deepest = Math.max(...used.map((s) => slices.indexOf(s)));
  return slices.slice(deepest + 1).find((s) => !blocked.has(s)) ?? null;
}

/** The drill path lives in the address (?drill=...), so the browser's Back returns to the previous level. */
export function readDrill(value: string | null): DrillStep[] {
  if (!value) return [];
  try {
    const steps: unknown = JSON.parse(value);
    if (!Array.isArray(steps) || steps.length > 10) return [];
    return steps.filter((s): s is [string, string | null] => Array.isArray(s) && typeof s[0] === 'string' && (typeof s[1] === 'string' || s[1] === null))
      .map(([slice, id]) => ({ slice, id }));
  } catch {
    return [];
  }
}

export function writeDrill(steps: DrillStep[]): string {
  return JSON.stringify(steps.map((s) => [s.slice, s.id]));
}

/** Body of POST drilldown: the path slices stay in the result so their names can head the breadcrumbs. */
export function drillQuery(query: ReportQuery, path: DrillStep[], next: string): ReportQuery & { path: DrillStep[] } {
  return { params: query.params, slice: [...path.map((s) => s.slice), next], compareWithPrevious: false, path };
}
