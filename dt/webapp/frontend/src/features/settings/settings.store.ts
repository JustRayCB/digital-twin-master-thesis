/**
 * @fileoverview Store management for the Settings feature.
 * Provides a structured way to edit actuator policies without raw JSON manipulation.
 */
import { derived, get, writable } from "svelte/store";
import { controllerClient } from "$shared/api";
import type { ActuatorConfigSet } from "$shared/types";

type LoadingState = "idle" | "loading" | "loaded" | "error" | "saving";

type ErrorState = {
	message: string;
	cause?: Error;
};

// Internal writable stores
const originalPolicies = writable<ActuatorConfigSet | null>(null);
const draftPolicies = writable<ActuatorConfigSet | null>(null);
const loadingStateData = writable<LoadingState>("idle");
const errorStateData = writable<ErrorState | null>(null);

// Public derived stores (read-only)
export const policies = derived(draftPolicies, ($draft) => $draft);
export const loadingState = derived(
	loadingStateData,
	($loadingState) => $loadingState,
);
export const errorState = derived(errorStateData, ($errorState) => $errorState);

/**
 * Checks if there are unsaved changes.
 */
export const isDirty = derived(
	[originalPolicies, draftPolicies],
	([$original, $draft]) => JSON.stringify($original) !== JSON.stringify($draft),
);

/**
 * Maps an unknown error to a structured ErrorState.
 */
function toErrorState(error: unknown): ErrorState {
	if (error instanceof Error) {
		return { message: error.message, cause: error };
	}
	return { message: String(error) };
}

/**
 * Loads actuator policies from the API and initializes the draft.
 */
export async function loadPolicies(): Promise<void> {
	loadingStateData.set("loading");
	errorStateData.set(null);

	try {
		const data = await controllerClient.fetchPolicies();
		originalPolicies.set(data);
		draftPolicies.set(JSON.parse(JSON.stringify(data))); // Deep clone for drafting
		loadingStateData.set("loaded");
	} catch (error) {
		console.error("Failed to load policies", error);
		loadingStateData.set("error");
		errorStateData.set(toErrorState(error));
	}
}

/**
 * Updates a specific part of the policy draft using a path-based approach.
 * Path is an array of strings representing the object structure.
 */
export function updatePolicy(path: string[], value: any): void {
	draftPolicies.update((current) => {
		if (!current) return current;
		const next = JSON.parse(JSON.stringify(current));
		let target = next;

		for (let i = 0; i < path.length - 1; i++) {
			const key = path[i];
			if (!(key in target)) target[key] = {};
			target = target[key];
		}

		target[path[path.length - 1]] = value;
		return next;
	});
}

/**
 * Saves modified actuator policies to the API.
 */
export async function savePolicies(): Promise<void> {
	const currentDraft = get(draftPolicies);
	if (!currentDraft) return;

	loadingStateData.set("saving");
	errorStateData.set(null);

	try {
		await controllerClient.updatePolicies(currentDraft);
		// On success, update the original to match the draft
		originalPolicies.set(JSON.parse(JSON.stringify(currentDraft)));
		loadingStateData.set("loaded");
	} catch (error) {
		console.error("Failed to save policies", error);
		loadingStateData.set("error");
		errorStateData.set(toErrorState(error));
	}
}

/**
 * Reverts the draft policies to the last saved state.
 */
export function resetDraft(): void {
	const original = get(originalPolicies);
	if (original) {
		draftPolicies.set(JSON.parse(JSON.stringify(original)));
	}
}

/**
 * Resets the store state.
 */
export function destroy(): void {
	originalPolicies.set(null);
	draftPolicies.set(null);
	loadingStateData.set("idle");
	errorStateData.set(null);
}
