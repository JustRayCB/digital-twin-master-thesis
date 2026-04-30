import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dt.analytics.features.base import FeatureSet
from dt.analytics.models.base import AnalyticsInferenceResult, OnlineModel
from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


@dataclass
class RLSState:
    """State container for Recursive Least Squares per plant.
    As per conventions, recent_data records store:
    - index 0: sensor value
    - index 1: (reserved/unused in this context, usually confidence or raw)
    - index 2: observation timestamp
    """

    # theta: [intercept, slope]
    theta: list[float] = field(default_factory=lambda: [0.0, 0.0])

    # P: Covariance matrix (2x2)
    # Initialized with large diagonal values indicating high initial uncertainty
    P: list[list[float]] = field(default_factory=lambda: [[1000.0, 0.0], [0.0, 1000.0]])

    # recent_data: list of tuples (value, metadata, timestamp)
    recent_data: list[tuple[float, Any, float]] = field(default_factory=list)

    # The timestamp of the first observation used as t=0 reference for this state
    t_start: float | None = None


class RecursiveLeastSquaresForecaster(OnlineModel):
    """
    Moisture forecast model using Recursive Least Squares (RLS) to learn the drying trend.
    Maintains internal state per plant.
    """

    def __init__(
        self,
        model_metadata: ModelMetadata | None = None,
        max_horizon_hours: int = 3,
        forgetting_factor: float = 0.99,
    ):
        self._model_metadata = model_metadata or ModelMetadata(
            model_name="moisture_forecaster",
            model_version="rls_v1",
        )
        self._max_horizon_hours = max_horizon_hours
        self._lambda = forgetting_factor
        self._state = RLSState()

    @property
    def model_metadata(self) -> ModelMetadata:
        return self._model_metadata

    @property
    def task_key(self) -> str:
        return "moisture_forecast"

    def predict(
        self, plant_id: str, features: FeatureSet, timestamp: datetime
    ) -> AnalyticsInferenceResult:
        """Run inference on the provided features using RLS."""

        current_moisture = features.features.get("soil_moisture.last")

        if current_moisture is None:
            return AnalyticsInferenceResult(
                model_metadata=self.model_metadata,
                task_key=self.task_key,
                timestamp=timestamp,
                plant_id=plant_id,
                outputs={"error": "Missing required feature: soil_moisture.last"},
                features_used=["soil_moisture.last"],
                metadata={"confidence": 0.0},
            )

        current_ts = timestamp.timestamp()
        state = self._state

        if state.t_start is None:
            state.t_start = current_ts

        # Calculate time difference in hours from start
        t_delta_hours = (current_ts - state.t_start) / 3600.0 if state.t_start is not None else 0.0

        # RLS Update
        # x_t = [1, t]
        x_t = [1.0, t_delta_hours]
        y_t = current_moisture

        # Compute x_t^T * P_{t-1}
        x_P = [
            x_t[0] * state.P[0][0] + x_t[1] * state.P[1][0],
            x_t[0] * state.P[0][1] + x_t[1] * state.P[1][1],
        ]

        # Compute x_t^T * P_{t-1} * x_t
        S = x_P[0] * x_t[0] + x_P[1] * x_t[1]

        # Gain K_t = P_{t-1} * x_t / (lambda + S)
        denominator = self._lambda + S

        # P_{t-1} * x_t
        P_x = [
            state.P[0][0] * x_t[0] + state.P[0][1] * x_t[1],
            state.P[1][0] * x_t[0] + state.P[1][1] * x_t[1],
        ]

        K_t = [P_x[0] / denominator, P_x[1] / denominator]

        # Error e_t = y_t - x_t^T * theta_{t-1}
        y_pred = x_t[0] * state.theta[0] + x_t[1] * state.theta[1]
        e_t = y_t - y_pred

        # Update theta: theta_t = theta_{t-1} + K_t * e_t
        state.theta[0] += K_t[0] * e_t
        state.theta[1] += K_t[1] * e_t

        # Update P: P_t = (P_{t-1} - K_t * x_t^T * P_{t-1}) / lambda
        # K_t * x_t^T is a 2x2 matrix
        K_x = [[K_t[0] * x_t[0], K_t[0] * x_t[1]], [K_t[1] * x_t[0], K_t[1] * x_t[1]]]

        # K_t * x_t^T * P_{t-1}
        K_x_P = [
            [
                K_x[0][0] * state.P[0][0] + K_x[0][1] * state.P[1][0],
                K_x[0][0] * state.P[0][1] + K_x[0][1] * state.P[1][1],
            ],
            [
                K_x[1][0] * state.P[0][0] + K_x[1][1] * state.P[1][0],
                K_x[1][0] * state.P[0][1] + K_x[1][1] * state.P[1][1],
            ],
        ]

        state.P[0][0] = (state.P[0][0] - K_x_P[0][0]) / self._lambda
        state.P[0][1] = (state.P[0][1] - K_x_P[0][1]) / self._lambda
        state.P[1][0] = (state.P[1][0] - K_x_P[1][0]) / self._lambda
        state.P[1][1] = (state.P[1][1] - K_x_P[1][1]) / self._lambda

        # Append to recent data buffer
        state.recent_data.append((current_moisture, None, current_ts))

        # Keep buffer bounded (e.g., last 24 records)
        if len(state.recent_data) > 24:
            state.recent_data.pop(0)

        horizon_hours = [self._max_horizon_hours]

        if len(state.recent_data) < 2:
            forecast = [current_moisture]
            uncertainty = [5.0 * h * (1.0 + (1.0 - features.confidence)) for h in horizon_hours]
        else:
            # Predict for future horizons
            # We predict at times t_delta_hours + h
            forecast = []
            uncertainty = []

            for h in horizon_hours:
                t_future = t_delta_hours + h

                # y = intercept + slope * t_future
                pred_val = state.theta[0] + state.theta[1] * t_future

                # Bound between 0 and 100
                pred_val = max(0.0, min(100.0, pred_val))
                forecast.append(pred_val)

                # Variance of prediction: x_f^T * P * x_f
                # x_f = [1, t_future]
                x_f = [1.0, t_future]
                var = x_f[0] * (state.P[0][0] * x_f[0] + state.P[0][1] * x_f[1]) + x_f[1] * (
                    state.P[1][0] * x_f[0] + state.P[1][1] * x_f[1]
                )

                # Base uncertainty scaled by confidence
                u = math.sqrt(abs(var)) * (1.0 + (1.0 - features.confidence))
                uncertainty.append(u)

        return AnalyticsInferenceResult(
            model_metadata=self.model_metadata,
            task_key=self.task_key,
            timestamp=timestamp,
            plant_id=plant_id,
            outputs={
                "horizon_hours": horizon_hours,
                "predicted_values": forecast,
                "uncertainty": uncertainty,
            },
            features_used=["soil_moisture.last"],
            metadata={"confidence": features.confidence},
        )
