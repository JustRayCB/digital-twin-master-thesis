import type {
	AnalyticsExportPayload,
	AnalyticsExportQuery,
	Recommendation,
} from "$shared/types";
import { HttpClient } from "./http.client";

export class AnalyticsClient {
	public constructor(private readonly http: HttpClient) {}

	public fetchRecommendationHistory(
		plantId: number,
		limit?: number,
	): Promise<Recommendation[]> {
		return this.http.get<Recommendation[]>("/api/analytics/recommendations", {
			plant_id: plantId,
			limit,
		});
	}

	public exportData(
		query: AnalyticsExportQuery,
	): Promise<AnalyticsExportPayload> {
		return this.http.get<AnalyticsExportPayload>("/api/analytics/export", {
			plant_id: query.plantId,
			since: query.since,
			until: query.until,
			limit: query.limit,
		});
	}
}
