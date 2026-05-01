/**
 * @fileoverview Global application state store.
 * Manages top-level state such as the current view, global navigation, and high-level feature toggles.
 */

import { writable } from "svelte/store";
import type { RoutineRecord, ViewState } from "$shared/types";

/** Store for tracking the currently active top-level view (e.g., OVERVIEW, ANALYTICS). */
export const currentView = writable<ViewState>("OVERVIEW");

/** Store holding the routine currently being edited in the Logic Builder, if any. */
export const routineDraft = writable<RoutineRecord | null>(null);

/** Store tracking the user's preference for plant visualization in the Overview. */
export const overviewViewMode = writable<"pixel" | "camera">("pixel");

/** Store tracking the selected camera angle in the Overview photo visualization. */
export const cameraSnapshotView = writable<"top" | "side">("top");

/** Store tracking whether the AI autopilot is globally enabled for the current context. */
export const autoPilotEnabled = writable(false);

/**
 * Changes the current top-level view.
 * @param view - The view state to navigate to.
 */
export function navigate(view: ViewState) {
  currentView.set(view);
}

/**
 * Transitions the application to the Logic Builder view and sets up a routine for editing.
 * @param routine - The routine record to edit. If null, a new routine is implicitly created.
 */
export function openRoutineBuilder(routine: RoutineRecord | null = null) {
  routineDraft.set(routine);
  currentView.set("LOGIC_BUILDER");
}
