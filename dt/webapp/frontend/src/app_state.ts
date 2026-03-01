import { writable } from "svelte/store";

import type { RoutineRecord, ViewState } from "./types";

export const currentView = writable<ViewState>("OVERVIEW");
export const routineDraft = writable<RoutineRecord | null>(null);

export function navigate(view: ViewState) {
  currentView.set(view);
}

export function openRoutineBuilder(routine: RoutineRecord | null = null) {
  routineDraft.set(routine);
  currentView.set("LOGIC_BUILDER");
}
