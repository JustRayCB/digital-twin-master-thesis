"""In-memory alert registry.

Maintains active alert state with deduplication, persistence counters,
cooldown timers, and acknowledgment flags.
"""

import time

from dt.analytics.alerts.state import AlertState
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)


class AlertRegistry:
    """Manages active alert state in memory.

    The registry tracks alert occurrences, implements persistence thresholds,
    manages cooldown periods, and handles acknowledgments and clearing.

    Alert ID Strategy:
    - Rule-based alerts: "{rule_id}:{source}" (e.g., "temp_high:temperature")
    - External submissions: use the alert_key provided in the incoming event

    Attributes
    ----------
    _states : dict[str, AlertState]
        Dictionary of active alerts keyed by alert_id.
    """

    def __init__(self) -> None:
        """Initialize the alert registry."""
        self._states: dict[str, AlertState] = {}

    def register(
        self,
        event: AlertHistoryEvent,
        persistence_count: int,
        cooldown_seconds: int,
    ) -> AlertStatus:
        """Register an alert event and return the resulting status.

        This method implements the core alert state machine:
        - Tracks occurrences until persistence threshold is reached
        - Suppresses alerts within cooldown period
        - Updates alerts that re-occur after cooldown

        Parameters
        ----------
        event : AlertHistoryEvent
            The alert history event to register (SensorAlertEvent or ExternalAlertEvent).
        persistence_count : int
            Number of consecutive violations required before alerting.
        cooldown_seconds : int
            Minimum time between repeated alerts for the same alert_key.

        Returns
        -------
        AlertStatus
            The alert status (ACTIVE for publishable events, IGNORED when suppressed/below threshold).
        """
        alert_key = event.alert_key
        current_time = time.time()

        # Extract rule_id and source from context
        rule_id = self._extract_rule_id(event)
        source = self._extract_source(event)

        # Check if alert already exists
        if alert_key in self._states:
            state = self._states[alert_key]

            # Check if alert has been created (reached persistence threshold)
            if state.cooldown_until is not None:
                # Alert is active - check cooldown
                if current_time < state.cooldown_until:
                    # Still in cooldown period - suppress
                    state.last_seen = current_time
                    state.correlation_id = event.correlation_id
                    state.message = event.message
                    state.occurrences += 1
                    return AlertStatus.IGNORED

                # Alert exists and is past cooldown - update it
                state.last_seen = current_time
                state.occurrences += 1
                state.correlation_id = event.correlation_id
                state.message = event.message
                state.cooldown_until = current_time + cooldown_seconds

                return AlertStatus.ACTIVE
            else:
                # Alert exists but hasn't reached persistence threshold yet
                # Continue tracking occurrences
                state.last_seen = current_time
                state.occurrences += 1
                state.correlation_id = event.correlation_id
                state.message = event.message

                # Check if we've now reached persistence threshold
                if state.occurrences >= persistence_count:
                    # Alert is now active
                    state.cooldown_until = current_time + cooldown_seconds
                    return AlertStatus.ACTIVE
                else:
                    # Still below threshold
                    return AlertStatus.IGNORED

        else:
            # New alert - check if we need to track or create
            # Create a new state to track occurrences
            state = AlertState(
                alert_id=alert_key,
                plant_id=event.plant_id,
                rule_id=rule_id,
                source=source,
                severity=event.severity,
                message=event.message,
                first_seen=current_time,
                last_seen=current_time,
                occurrences=1,
                acknowledged=False,
                acknowledged_by=None,
                cooldown_until=None,  # Will be set if alert is created
                correlation_id=event.correlation_id,
            )

            self._states[alert_key] = state

            # Check if we've reached persistence threshold
            if state.occurrences >= persistence_count:
                # Alert is now active
                state.cooldown_until = current_time + cooldown_seconds
                return AlertStatus.ACTIVE
            else:
                # Still below threshold
                return AlertStatus.IGNORED

    def _extract_rule_id(self, event: AlertHistoryEvent) -> str | None:
        """Extract rule_id from alert event.

        For rule-based alerts, the alert_key format is "{rule_id}:{source}".
        For external alerts, returns None.

        Parameters
        ----------
        event : AlertHistoryEvent
            The alert event.

        Returns
        -------
        str | None
            The rule ID if available, None otherwise.
        """
        if isinstance(event, SensorAlertEvent):
            # Parse rule_id from alert_key (format: "rule_id:source")
            parts = event.alert_key.split(":", 1)
            return parts[0] if len(parts) > 1 else None
        return None

    def _extract_source(self, event: AlertHistoryEvent) -> str:
        """Extract source from alert event.

        Parameters
        ----------
        event : AlertHistoryEvent
            The alert event.

        Returns
        -------
        str
            The source (topic short name for sensor alerts, parsed from alert_key otherwise).
        """
        if isinstance(event, SensorAlertEvent):
            return event.reading.topic.short_name
        elif isinstance(event, ExternalAlertEvent):
            # Parse source from alert_key (format: "rule_id:source" or just source)
            parts = event.alert_key.split(":", 1)
            return parts[1] if len(parts) > 1 else parts[0]
        return "unknown"

    def acknowledge(self, alert_id: str, actor: str) -> bool:
        """Acknowledge an alert.

        Parameters
        ----------
        alert_id : str
            The alert ID to acknowledge.
        actor : str
            Identifier of the actor acknowledging the alert.

        Returns
        -------
        bool
            True if alert was acknowledged, False if alert doesn't exist.
        """
        if alert_id not in self._states:
            return False

        state = self._states[alert_id]
        state.acknowledged = True
        state.acknowledged_by = actor

        return True

    def clear(self, alert_id: str) -> bool:
        """Clear an alert from the registry.

        Parameters
        ----------
        alert_id : str
            The alert ID to clear.

        Returns
        -------
        bool
            True if alert was cleared, False if alert doesn't exist.
        """
        if alert_id not in self._states:
            return False

        del self._states[alert_id]
        return True

    def get_alert_state(self, alert_key: str) -> AlertState | None:
        """Get alert state by alert key.

        Parameters
        ----------
        alert_key : str
            The alert key to retrieve.

        Returns
        -------
        AlertState | None
            The alert state if found, None otherwise.
        """
        return self._states.get(alert_key)

    def restore_state(self, events: list[AlertHistoryEvent]) -> None:
        """Restore registry state from a list of active alert events.

        Used on startup to hydrate the in-memory registry from the persistent
        database state.

        Parameters
        ----------
        events : list[AlertHistoryEvent]
            List of active alert events fetched from the database.
        """
        current_time = time.time()
        for event in events:
            # Reconstruct AlertState from the event
            rule_id = self._extract_rule_id(event)
            source = self._extract_source(event)

            state = AlertState(
                alert_id=event.alert_key,
                plant_id=event.plant_id,
                rule_id=rule_id,
                source=source,
                severity=event.severity,
                message=event.message,
                first_seen=event.timestamp,
                last_seen=event.timestamp,
                occurrences=1,  # Assume at least 1, actual count lost on restart
                acknowledged=event.status == AlertStatus.ACKNOWLEDGED,
                acknowledged_by=event.acknowledged_by,
                cooldown_until=current_time,  # Expire cooldown so next reading updates it
                correlation_id=event.correlation_id,
            )

            self._states[event.alert_key] = state
