/**
 * @fileoverview Barrel export and singleton initialization for API clients.
 * Provides pre-configured, singleton instances of all HTTP clients for use across the application.
 */

import { AnalyticsClient } from "./analytics.client";
import { ControllerClient } from "./controller.client";
import { DbClient } from "./db.client";
import { HttpClient } from "./http.client";

const defaultHttpClient = new HttpClient();

/** Singleton instance of the DbClient. */
export const dbClient = new DbClient(defaultHttpClient);
/** Singleton instance of the AnalyticsClient. */
export const analyticsClient = new AnalyticsClient(defaultHttpClient);
/** Singleton instance of the ControllerClient. */
export const controllerClient = new ControllerClient(defaultHttpClient);

export { AnalyticsClient } from "./analytics.client";
export { ControllerClient } from "./controller.client";
export { DbClient } from "./db.client";
export { HttpClient } from "./http.client";
