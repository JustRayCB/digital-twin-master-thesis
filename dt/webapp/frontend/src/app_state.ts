import { writable } from "svelte/store";

import type { ViewState } from "./types";

export const currentView = writable<ViewState>("OVERVIEW");

export function navigate(view: ViewState) {
  currentView.set(view);
}

