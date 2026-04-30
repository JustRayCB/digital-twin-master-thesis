/**
 * @fileoverview Transformation helpers for the Overview feature.
 */

import type { Routine, RoutineRecord } from "$shared/types";

function formatRoutineCondition(routine: RoutineRecord): string {
  return routine.enabled ? "Enabled" : "Disabled";
}

/**
 * Maps a backend RoutineRecord into the view-model representation used by Overview cards.
 */
export function mapRoutine(routine: RoutineRecord): Routine {
  return {
    id: routine.id,
    name: routine.name,
    condition: formatRoutineCondition(routine),
    active: routine.enabled,
    graph: routine.graph,
    plant_id: routine.plant_id,
  };
}
