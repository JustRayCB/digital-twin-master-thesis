"""Deterministic baseline classifier for plant health."""

from datetime import datetime
from enum import IntEnum
from typing import NamedTuple

from dt.analytics.features.base import FeatureSet
from dt.analytics.models.base import AnalyticsInferenceResult
from dt.communication.dataclasses.analytics.health_assessment import \
    HealthState
from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


class SignalSeverity(IntEnum):
    NONE = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3


class SignalEvaluation(NamedTuple):
    severity: SignalSeverity
    reasons: tuple[str, ...]


class ObservabilityEvaluation(NamedTuple):
    confidence: float | None
    unknown: bool
    blocks_healthy: bool
    reasons: tuple[str, ...]


class PlantHealthBaselineModel:
    """A deterministic baseline model for plant health."""

    def __init__(self, model_metadata: ModelMetadata | None = None):
        self._model_metadata = model_metadata or ModelMetadata(
            model_name="plant_health_baseline",
            model_version="v1",
        )
        self._task_key = "plant_health"

    @property
    def model_metadata(self) -> ModelMetadata:
        return self._model_metadata

    @property
    def task_key(self) -> str:
        return self._task_key

    def predict(
        self, plant_id: str, features: FeatureSet, timestamp: datetime
    ) -> AnalyticsInferenceResult:
        """Evaluate grouped signals and return a health classification."""
        hydration = self._evaluate_hydration(features)
        atmosphere = self._evaluate_atmosphere(features)
        vitality = self._evaluate_vitality(features)
        observability = self._evaluate_observability(features)

        reasons = [
            *hydration.reasons,
            *atmosphere.reasons,
            *vitality.reasons,
            *observability.reasons,
        ]

        if observability.unknown:
            state = HealthState.UNKNOWN
            score = None
        else:
            state = self._combine_signal_state(hydration, atmosphere, vitality)
            score = self._score_from_signal_state(state, hydration, atmosphere, vitality)
            if observability.blocks_healthy and state is HealthState.HEALTHY:
                state = HealthState.STRESSED

        summary = "; ".join(reasons) if reasons else "Signals remain within baseline ranges"

        return AnalyticsInferenceResult(
            model_metadata=self.model_metadata,
            task_key=self.task_key,
            timestamp=timestamp,
            plant_id=plant_id,
            outputs={
                "state": state.value,
                "score": score,
                "confidence": observability.confidence,
                "summary": summary,
            },
            features_used=[key for key, value in features.features.items() if value is not None],
            metadata={"drivers": len(reasons)},
        )

    def _evaluate_hydration(self, features: FeatureSet) -> SignalEvaluation:
        # Soil moisture bands here are local STEMMA-derived processed percentages,
        # not universal basil agronomy cutoffs. They are tuned to this sensor path's
        # processed output and should be read with the local hardware caveat from
        # https://learn.adafruit.com/adafruit-stemma-soil-sensor-i2c-capacitive-moisture-sensor?view=all
        soil_last = features.features.get("soil_moisture.last")
        soil_mean = features.features.get("soil_moisture.mean")
        soil_delta = features.features.get("soil_moisture.delta")
        drop_rate = features.features.get("context.soil_moisture_drop_rate_24h")
        dry_persistence = features.features.get("context.raw_dry_threshold_persistence_24h")

        moisture_values = [value for value in (soil_last, soil_mean) if value is not None]
        if not moisture_values:
            return SignalEvaluation(SignalSeverity.NONE, ())

        severity = SignalSeverity.NONE
        reasons: list[str] = []
        moisture_floor = min(moisture_values)
        moisture_ceiling = max(moisture_values)

        # Detect dryness
        if moisture_floor <= 30.0:
            severity = SignalSeverity.SEVERE
            reasons.append(f"soil moisture is critically dry ({moisture_floor:.1f}%)")
        elif moisture_floor < 45.0:
            severity = max(severity, SignalSeverity.MODERATE)
            reasons.append(f"soil moisture is dry ({moisture_floor:.1f}%)")

        # Detect saturation
        if moisture_ceiling >= 90.0:
            severity = SignalSeverity.SEVERE
            reasons.append(f"soil moisture is saturated ({moisture_ceiling:.1f}%)")
        elif moisture_ceiling > 80.0:
            severity = max(severity, SignalSeverity.MODERATE)
            reasons.append(f"soil moisture is elevated ({moisture_ceiling:.1f}%)")

        # Escalate only when current dryness is supported by both a falling trend
        # and a strongly persistent dry context over the last 24h.
        if moisture_floor < 45.0:
            falling_now = soil_delta is not None and soil_delta <= -4.0
            falling_over_day = drop_rate is not None and drop_rate <= -3.0
            persistent_dry = dry_persistence is not None and dry_persistence >= 0.85

            if falling_now:
                reasons.append(f"soil moisture is still falling ({soil_delta:.1f} points)")
            if falling_over_day:
                reasons.append(f"24h moisture drop rate is steep ({drop_rate:.1f})")
            if persistent_dry:
                reasons.append(f"dry threshold persisted for {dry_persistence:.2f} of the last 24h")

            if (
                severity == SignalSeverity.MODERATE
                and persistent_dry
                and (falling_now or falling_over_day)
            ):
                severity = SignalSeverity.SEVERE

        return SignalEvaluation(severity, tuple(reasons))

    def _evaluate_atmosphere(self, features: FeatureSet) -> SignalEvaluation:
        # Climate thresholds below are literature-backed heuristic bands for basil
        # greenhouse operation rather than a cultivar-specific calibration. Low-VPD /
        # high-humidity wet-risk guidance comes from
        # https://drygair.com/blog/how-to-optimize-greenhouse-humidity-maximum-crop-yield-comprehensive-guide/
        # https://ag.umass.edu/vegetable/fact-sheets/basil-downy-mildew
        # https://ipm.cahnr.uconn.edu/downy-mildew-of-basil/
        # https://ipm.cahnr.uconn.edu/wp-content/uploads/sites/3216/2022/12/2021basildownymildewghs.pdf
        # Temperature comfort / stress bands are anchored to basil production and
        # stress literature:
        # https://journals.ashs.org/hortsci/view/journals/hortsci/54/11/article-p1915.xml
        # https://www.producegrower.com/article/hydroponic-production-primer-managing-basil-production-throughout-the-year/
        # https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0294905
        temperature_last = features.features.get("temperature.last")
        temperature_mean = features.features.get("temperature.mean")
        humidity_last = features.features.get("humidity.last")
        humidity_mean = features.features.get("humidity.mean")
        vpd = features.features.get("context.vpd_kpa_24h")

        temperature_values = [
            value for value in (temperature_last, temperature_mean) if value is not None
        ]
        humidity_values = [value for value in (humidity_last, humidity_mean) if value is not None]

        severity = SignalSeverity.NONE
        reasons: list[str] = []

        if vpd is not None:
            if vpd <= 0.4:
                severity = max(severity, SignalSeverity.SEVERE)
                reasons.append(f"24h VPD is very low and favors wet pressure ({vpd:.2f} kPa)")
            elif vpd < 0.5:
                severity = max(severity, SignalSeverity.MODERATE)
                reasons.append(f"24h VPD is low enough to raise wet-risk pressure ({vpd:.2f} kPa)")
            elif vpd < 0.7:
                severity = max(severity, SignalSeverity.MILD)
                reasons.append(f"24h VPD is below the comfort range ({vpd:.2f} kPa)")
            elif vpd >= 2.2:
                severity = max(severity, SignalSeverity.SEVERE)
                reasons.append(f"24h VPD is very high ({vpd:.2f} kPa)")
            elif vpd > 1.5:
                severity = max(severity, SignalSeverity.MODERATE)
                reasons.append(f"24h VPD is elevated ({vpd:.2f} kPa)")
            elif vpd > 1.1:
                severity = max(severity, SignalSeverity.MILD)
                reasons.append(f"24h VPD is above the comfort range ({vpd:.2f} kPa)")

        if temperature_values:
            hottest = max(temperature_values)
            coldest = min(temperature_values)
            if hottest >= 35.0 or coldest <= 12.0:
                severity = max(severity, SignalSeverity.SEVERE)
                reasons.append(
                    f"temperature is far outside the basil baseline range ({coldest:.1f}-{hottest:.1f}C)"
                )
            elif hottest >= 30.0 or coldest <= 18.0:
                severity = max(severity, SignalSeverity.MODERATE)
                reasons.append(
                    f"temperature is outside the basil comfort range ({coldest:.1f}-{hottest:.1f}C)"
                )

        if humidity_values:
            driest = min(humidity_values)
            wettest = max(humidity_values)
            if vpd is None:
                if wettest >= 90.0:
                    severity = max(severity, SignalSeverity.SEVERE)
                    reasons.append(
                        f"humidity is in strong wet-risk territory without VPD ({driest:.1f}-{wettest:.1f}%)"
                    )
                elif wettest > 85.0:
                    severity = max(severity, SignalSeverity.MODERATE)
                    reasons.append(
                        f"humidity is in wet-risk territory without VPD ({driest:.1f}-{wettest:.1f}%)"
                    )
                elif driest <= 30.0:
                    severity = max(severity, SignalSeverity.MODERATE)
                    reasons.append(
                        f"humidity is dry without VPD context ({driest:.1f}-{wettest:.1f}%)"
                    )
            elif driest <= 25.0 or wettest >= 90.0:
                severity = max(severity, SignalSeverity.MILD)
                reasons.append(
                    f"humidity is supporting atmospheric risk ({driest:.1f}-{wettest:.1f}%)"
                )

        return SignalEvaluation(severity, tuple(reasons))

    def _evaluate_vitality(self, features: FeatureSet) -> SignalEvaluation:
        green_last = features.features.get("green_ratio.last")
        green_delta = features.features.get("green_ratio.delta")
        leaf_count_delta_24h = features.features.get("context.leaf_count_delta_24h")
        plant_height_delta_24h = features.features.get("context.plant_height_delta_24h")

        severity = SignalSeverity.NONE
        reasons: list[str] = []

        if green_last is not None:
            if green_last <= 30.0:
                severity = SignalSeverity.SEVERE
                reasons.append(f"green ratio is very low ({green_last:.2f})")
            elif green_last <= 60.0:
                severity = max(severity, SignalSeverity.MODERATE)
                reasons.append(f"green ratio is low ({green_last:.2f})")

        if green_delta is not None:
            if green_delta <= -7.0:
                severity = max(severity, SignalSeverity.SEVERE)
                reasons.append(f"green ratio is declining quickly ({green_delta:.2f})")
            elif green_delta <= -3.0:
                severity = max(severity, SignalSeverity.MILD)
                reasons.append(f"green ratio is declining ({green_delta:.2f})")

        if severity > SignalSeverity.NONE:
            leaf_count_declined = leaf_count_delta_24h is not None and leaf_count_delta_24h < 0.0
            plant_height_declined = (
                plant_height_delta_24h is not None and plant_height_delta_24h < 0.0
            )

            if leaf_count_declined:
                reasons.append(
                    f"leaf count declined over 24h and corroborates vitality stress ({leaf_count_delta_24h:.2f})"
                )
            if plant_height_declined:
                reasons.append(
                    f"plant height declined over 24h and corroborates vitality stress ({plant_height_delta_24h:.2f})"
                )

            if leaf_count_declined and plant_height_declined:
                severity = max(severity, SignalSeverity.SEVERE)
            elif leaf_count_declined or plant_height_declined:
                severity = max(severity, SignalSeverity.MODERATE)

        return SignalEvaluation(severity, tuple(reasons))

    def _evaluate_observability(self, features: FeatureSet) -> ObservabilityEvaluation:
        coverage = features.features.get("quality.coverage_ratio")
        freshness = features.features.get("quality.freshness_ratio")
        window_dq = features.features.get("quality.window_dq_mean")
        imputation_burden = features.features.get("quality.imputation_burden")

        hydration_evidence = any(
            features.features.get(name) is not None
            for name in (
                "soil_moisture.last",
                "soil_moisture.mean",
                "soil_moisture.delta",
                "context.soil_moisture_drop_rate_24h",
                "context.raw_dry_threshold_persistence_24h",
            )
        )
        atmosphere_evidence = any(
            features.features.get(name) is not None
            for name in (
                "temperature.last",
                "temperature.mean",
                "humidity.last",
                "humidity.mean",
                "context.vpd_kpa_24h",
            )
        )
        vitality_evidence = any(
            features.features.get(name) is not None
            for name in ("green_ratio.last", "green_ratio.delta")
        )
        evidence_groups = sum((hydration_evidence, atmosphere_evidence, vitality_evidence))

        quality_inputs: list[float] = []
        reasons: list[str] = []

        if features.confidence is not None:
            quality_inputs.append(float(features.confidence))

        # If any of the core quality metrics are missing,
        # we fall back to conservative default values that will limit confidence and healthy classification
        # but not block insights entirely.
        missing_quality_inputs = 0
        for quality_value, fallback_value in (
            (coverage, 0.35),
            (freshness, 0.35),
            (window_dq, 0.45),
            (None if imputation_burden is None else 1.0 - imputation_burden, 0.4),
        ):
            if quality_value is None:
                missing_quality_inputs += 1
                quality_inputs.append(fallback_value)
            else:
                quality_inputs.append(quality_value)

        confidence = None
        if quality_inputs:
            average_quality = self._clamp(sum(quality_inputs) / len(quality_inputs))
            if features.confidence is not None:
                confidence = min(float(features.confidence), average_quality)
            else:
                confidence = average_quality

        # Minimum 2 signal groups with evidence to avoid unknown classification, and hydration is required since it's a core plant need and the most direct signal of health.
        if not hydration_evidence or evidence_groups < 2:
            reasons.append("insufficient evidence across hydration and supporting health signals")
            if not hydration_evidence:
                reasons.append("hydration evidence is missing")
            return ObservabilityEvaluation(confidence, True, True, tuple(reasons))

        # If confidence is very low, we classify as unknown and block healthy classification,
        if confidence is not None and confidence < 0.15:
            if coverage is not None and coverage < 0.3:
                reasons.append(f"coverage is too low ({coverage:.2f})")
            if freshness is not None and freshness < 0.3:
                reasons.append(f"data is stale ({freshness:.2f} freshness)")
            return ObservabilityEvaluation(confidence, True, True, tuple(reasons))

        blocks_healthy = False
        # If the data quality is "okay but not great" (confidence between 0.15 and 0.6)
        # we allow the model to classify as stressed or critical, but not healthy.
        if (
            (coverage is not None and coverage < 0.3)
            or (freshness is not None and freshness < 0.3)
            or (window_dq is not None and window_dq < 0.5)
            or (imputation_burden is not None and imputation_burden > 0.6)
            or missing_quality_inputs >= 2
            or (confidence is not None and confidence < 0.6)
        ):
            blocks_healthy = True
            if coverage is not None and coverage < 0.3:
                reasons.append(f"coverage is limited ({coverage:.2f})")
            if freshness is not None and freshness < 0.3:
                reasons.append(f"data freshness is low ({freshness:.2f})")
            if window_dq is not None and window_dq < 0.5:
                reasons.append(f"window data quality is weak ({window_dq:.2f})")
            if imputation_burden is not None and imputation_burden > 0.6:
                reasons.append(f"imputation burden is high ({imputation_burden:.2f})")
            if missing_quality_inputs >= 2:
                reasons.append("observability quality inputs are incomplete")
            if confidence is not None and confidence < 0.6:
                reasons.append(f"assessment confidence is limited ({confidence:.2f})")

        return ObservabilityEvaluation(confidence, False, blocks_healthy, tuple(reasons))

    def _combine_signal_state(
        self,
        hydration: SignalEvaluation,
        atmosphere: SignalEvaluation,
        vitality: SignalEvaluation,
    ) -> HealthState:
        severities = [hydration.severity, atmosphere.severity, vitality.severity]
        moderate_count = sum(severity >= SignalSeverity.MODERATE for severity in severities)
        mild_count = sum(severity == SignalSeverity.MILD for severity in severities)

        if (
            hydration.severity == SignalSeverity.SEVERE
            or vitality.severity == SignalSeverity.SEVERE
        ):
            return HealthState.CRITICAL
        if moderate_count >= 2:
            return HealthState.CRITICAL
        if moderate_count >= 1 or mild_count >= 2:
            return HealthState.STRESSED
        return HealthState.HEALTHY

    def _score_from_signal_state(
        self,
        state: HealthState,
        hydration: SignalEvaluation,
        atmosphere: SignalEvaluation,
        vitality: SignalEvaluation,
    ) -> float:
        severities = [hydration.severity, atmosphere.severity, vitality.severity]
        moderate_count = sum(severity >= SignalSeverity.MODERATE for severity in severities)
        mild_count = sum(severity == SignalSeverity.MILD for severity in severities)

        if state is HealthState.CRITICAL:
            if (
                hydration.severity == SignalSeverity.SEVERE
                or vitality.severity == SignalSeverity.SEVERE
            ):
                return 0.2
            return 0.3
        if state is HealthState.STRESSED:
            if moderate_count >= 1:
                return 0.55
            if mild_count >= 2:
                return 0.68
            return 0.55
        return 0.85

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))
