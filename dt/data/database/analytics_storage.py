from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import text

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.analytics.forecast_result import ForecastResult
from dt.communication.dataclasses.analytics.health_assessment import HealthAssessment
from dt.communication.dataclasses.analytics.recommendation import Recommendation
from dt.communication.dataclasses.queries import (
    ForecastHistoryQuery,
    HealthHistoryQuery,
    RecommendationHistoryQuery,
)
from dt.data.database.base_storage import DatabaseStorage


class AnalyticsStorage(DatabaseStorage, ABC):
    """Storage capability for analytics outputs and recommendation lifecycle."""

    @abstractmethod
    def log_health_assessment(self, assessment: HealthAssessment) -> None:
        ...

    @abstractmethod
    def get_health_history(self, query: HealthHistoryQuery) -> list[HealthAssessment]:
        ...

    @abstractmethod
    def log_forecast_result(self, forecast: ForecastResult) -> None:
        ...

    @abstractmethod
    def get_forecast_history(self, query: ForecastHistoryQuery) -> list[ForecastResult]:
        ...

    @abstractmethod
    def log_recommendation(self, recommendation: Recommendation) -> None:
        ...

    @abstractmethod
    def get_recommendation_history(
        self, query: RecommendationHistoryQuery
    ) -> list[Recommendation]:
        ...


class AnalyticsStore(AnalyticsStorage):
    """Persistence for analytics assessments, forecasts, and recommendation lifecycle rows."""

    def log_health_assessment(self, assessment: HealthAssessment) -> None:
        data = dump("db_row", assessment)
        query = """
            INSERT INTO analytics_health_assessments (
                plant_id, correlation_id, assessed_at, state, score,
                summary, confidence, model_metadata
            ) VALUES (
                :plant_id, :correlation_id, to_timestamp(:timestamp), :state, :score,
                :summary, :confidence, :model_metadata
            )
        """
        with self._get_connection() as conn:
            conn.execute(text(query), data)

    def get_health_history(self, query: HealthHistoryQuery) -> list[HealthAssessment]:
        filters = ["plant_id = :plant_id"]
        params: dict[str, Any] = {"plant_id": query.plant_id}
        if query.since is not None:
            filters.append("assessed_at >= to_timestamp(:since)")
            params["since"] = query.since
        if query.until is not None:
            filters.append("assessed_at <= to_timestamp(:until)")
            params["until"] = query.until
        if query.correlation_id is not None:
            filters.append("correlation_id = :correlation_id")
            params["correlation_id"] = query.correlation_id

        limit_clause = " LIMIT :limit" if query.limit is not None else ""
        if query.limit is not None:
            params["limit"] = query.limit

        sql = f"""
            SELECT
                plant_id, correlation_id, assessed_at AS timestamp, state, score,
                summary, confidence, model_metadata
            FROM analytics_health_assessments
            WHERE {' AND '.join(filters)}
            ORDER BY assessed_at DESC, id DESC
            {limit_clause}
        """
        with self._get_connection() as conn:
            rows = conn.execute(text(sql), params).fetchall()
            return [load("db_row", HealthAssessment, row) for row in rows]

    def log_forecast_result(self, forecast: ForecastResult) -> None:
        data = dump("db_row", forecast)
        query = """
            INSERT INTO analytics_forecast_results (
                plant_id, correlation_id, forecast_at, metric, horizon_seconds,
                predicted_value, unit, features_used, inference_metadata, model_metadata
            ) VALUES (
                :plant_id, :correlation_id, to_timestamp(:timestamp), :metric, :horizon_seconds,
                :predicted_value, :unit, :features_used, :inference_metadata, :model_metadata
            )
        """
        with self._get_connection() as conn:
            conn.execute(text(query), data)

    def get_forecast_history(self, query: ForecastHistoryQuery) -> list[ForecastResult]:
        filters = ["plant_id = :plant_id"]
        params: dict[str, Any] = {"plant_id": query.plant_id}
        if query.since is not None:
            filters.append("forecast_at >= to_timestamp(:since)")
            params["since"] = query.since
        if query.until is not None:
            filters.append("forecast_at <= to_timestamp(:until)")
            params["until"] = query.until
        if query.correlation_id is not None:
            filters.append("correlation_id = :correlation_id")
            params["correlation_id"] = query.correlation_id
        if query.metric is not None:
            filters.append("metric = :metric")
            params["metric"] = query.metric
        if query.horizon_seconds is not None:
            filters.append("horizon_seconds = :horizon_seconds")
            params["horizon_seconds"] = query.horizon_seconds

        limit_clause = " LIMIT :limit" if query.limit is not None else ""
        if query.limit is not None:
            params["limit"] = query.limit

        sql = f"""
            SELECT
                plant_id, correlation_id, forecast_at AS timestamp, metric, horizon_seconds,
                predicted_value, unit, features_used, inference_metadata, model_metadata
            FROM analytics_forecast_results
            WHERE {' AND '.join(filters)}
            ORDER BY forecast_at DESC, id DESC
            {limit_clause}
        """
        with self._get_connection() as conn:
            rows = conn.execute(text(sql), params).fetchall()
            return [load("db_row", ForecastResult, row) for row in rows]

    def log_recommendation(self, recommendation: Recommendation) -> None:
        data = dump("db_row", recommendation)
        self._upsert_recommendation_lifecycle(
            {
                "plant_id": data["plant_id"],
                "correlation_id": data["correlation_id"],
                "recommended_at": data["timestamp"],
                "actions": data["actions"],
                "recommendation_confidence": data["confidence"],
                "recommendation_reason": data["reason"],
                "recommendation_model_metadata": data["model_metadata"],
                "action_results": data["action_results"],
                "decided_at": data["timestamp"],
            }
        )

    def get_recommendation_history(
        self, query: RecommendationHistoryQuery
    ) -> list[Recommendation]:
        filters = ["plant_id = :plant_id"]
        params: dict[str, Any] = {"plant_id": query.plant_id}
        timestamp_expr = "COALESCE(decided_at, recommended_at)"
        if query.since is not None:
            filters.append(f"{timestamp_expr} >= to_timestamp(:since)")
            params["since"] = query.since
        if query.until is not None:
            filters.append(f"{timestamp_expr} <= to_timestamp(:until)")
            params["until"] = query.until
        if query.correlation_id is not None:
            filters.append("correlation_id = :correlation_id")
            params["correlation_id"] = query.correlation_id

        limit_clause = " LIMIT :limit" if query.limit is not None else ""
        if query.limit is not None:
            params["limit"] = query.limit

        sql = f"""
            SELECT
                plant_id, correlation_id, {timestamp_expr} AS timestamp,
                recommendation_reason AS reason,
                recommendation_confidence AS confidence,
                recommendation_model_metadata AS model_metadata,
                actions, action_results
            FROM recommendation_lifecycle
            WHERE {' AND '.join(filters)}
            ORDER BY {timestamp_expr} DESC, id DESC
            {limit_clause}
        """
        with self._get_connection() as conn:
            rows = conn.execute(text(sql), params).fetchall()
            return [load("db_row", Recommendation, row) for row in rows]

    def _upsert_recommendation_lifecycle(self, data: dict[str, Any]) -> None:
        query = """
            INSERT INTO recommendation_lifecycle (
                plant_id, correlation_id, recommended_at, actions,
                recommendation_confidence, recommendation_reason,
                recommendation_model_metadata, action_results, decided_at
            ) VALUES (
                :plant_id, :correlation_id, to_timestamp(:recommended_at), :actions,
                :recommendation_confidence, :recommendation_reason,
                :recommendation_model_metadata, :action_results, to_timestamp(:decided_at)
            )
            ON CONFLICT (plant_id, correlation_id) DO UPDATE SET
                recommended_at = EXCLUDED.recommended_at,
                actions = EXCLUDED.actions,
                recommendation_confidence = EXCLUDED.recommendation_confidence,
                recommendation_reason = EXCLUDED.recommendation_reason,
                recommendation_model_metadata = EXCLUDED.recommendation_model_metadata,
                action_results = EXCLUDED.action_results,
                decided_at = EXCLUDED.decided_at
        """
        with self._get_connection() as conn:
            conn.execute(text(query), data)
