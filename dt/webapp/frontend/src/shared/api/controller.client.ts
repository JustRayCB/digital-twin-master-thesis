import type {
	ActuatorConfigSet,
	ActionDispatchPayload,
	ActionHistoryRecord,
	ControlMode,
	ControlModeUpdate,
	RoutineRecord,
	RoutineUpdatePayload,
} from "$shared/types";
import { HttpClient } from "./http.client";

export class ControllerClient {
	public constructor(private readonly http: HttpClient) {}

	public fetchActionHistory(
		plantId: number,
		limit?: number,
	): Promise<ActionHistoryRecord[]> {
		return this.http.get<ActionHistoryRecord[]>(
			"/api/controller/actions/history",
			{
				plant_id: plantId,
				limit,
			},
		);
	}

	public dispatchAction(
		payload: ActionDispatchPayload,
	): Promise<{ status: string }> {
		return this.http.post<{ status: string }>(
			"/api/controller/actions/dispatch",
			payload,
		);
	}

	public fetchRoutines(plantId?: number): Promise<RoutineRecord[]> {
		return this.http.get<RoutineRecord[]>("/api/controller/routines", {
			plant_id: plantId,
		});
	}

	public createRoutine(
		payload: RoutineUpdatePayload,
	): Promise<{ id: number; status: string }> {
		return this.http.post<{ id: number; status: string }>(
			"/api/controller/routines",
			payload,
		);
	}

	public updateRoutine(
		routineId: number,
		payload: RoutineUpdatePayload,
	): Promise<{ status: string }> {
		return this.http.put<{ status: string }>(
			`/api/controller/routines/${routineId}`,
			payload,
		);
	}

	public deleteRoutine(routineId: number): Promise<{ status: string }> {
		return this.http.delete<{ status: string }>(
			`/api/controller/routines/${routineId}`,
		);
	}

	public fetchControlMode(plantId: number): Promise<ControlMode> {
		return this.http.get<ControlMode>("/api/controller/mode", {
			plant_id: plantId,
		});
	}

	public updateControlMode(
		payload: ControlModeUpdate,
	): Promise<{ status: string }> {
		return this.http.put<{ status: string }>("/api/controller/mode", payload);
	}

	/**
	 * Fetches the global actuator policies.
	 */
	public fetchPolicies(): Promise<ActuatorConfigSet> {
		return this.http.get<ActuatorConfigSet>("/api/controller/policies");
	}

	/**
	 * Updates the global actuator policies.
	 * @param policies - The new policy configuration set.
	 */
	public updatePolicies(
		policies: ActuatorConfigSet,
	): Promise<{ status: string }> {
		return this.http.put<{ status: string }>(
			"/api/controller/policies",
			policies,
		);
	}
}
