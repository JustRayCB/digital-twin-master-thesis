"""In-memory alert registry.

Maintains active alert state with deduplication, persistence counters,
cooldown timers, and acknowledgment flags.
"""

import time

from dt.alerts.state.models import AlertLifecycleEvent, AlertState
from dt.communication.dataclasses.alerts import CandidateAlert


class AlertRegistry:
    """Manages active alert state in memory.

    The registry tracks alert occurrences, implements persistence thresholds,
    manages cooldown periods, and handles acknowledgments and clearing.

    Alert ID Strategy:
    - Rule-based alerts: "{rule_id}:{source}" (e.g., "temp_high:temperature")
    - External submissions: use the alert_id provided in CandidateAlert

    Attributes
    ----------
    _states : dict[str, AlertState]
        Dictionary of active alerts keyed by alert_id.
    """

    def __init__(self) -> None:
        """Initialize the alert registry."""
        self._states: dict[str, AlertState] = {}

    def register(self, candidate: CandidateAlert) -> AlertLifecycleEvent:
        """Register a candidate alert and return the lifecycle event.

        This method implements the core alert state machine:
        - Tracks occurrences until persistence threshold is reached
        - Suppresses alerts within cooldown period
        - Updates alerts that re-occur after cooldown

        Parameters
        ----------
        candidate : CandidateAlert
            The candidate alert to register.

        Returns
        -------
        AlertLifecycleEvent
            The lifecycle event (CREATED, UPDATED, SUPPRESSED, or IGNORED).
        """
        alert_id = candidate.alert_id
        persistence_count = candidate.persistence_count
        cooldown_seconds = candidate.cooldown_seconds
        current_time = time.time()

        # Check if alert already exists
        if alert_id in self._states:
            state = self._states[alert_id]

            # Check if alert has been created (reached persistence threshold)
            if state.cooldown_until is not None:
                # Alert is active - check cooldown
                if current_time < state.cooldown_until:
                    # Still in cooldown period - suppress
                    # TODO: Need to decide if we update the state when suppressed
                    state.last_seen = current_time
                    state.correlation_id = candidate.correlation_id
                    state.message = candidate.message
                    state.occurrences += 1
                    return AlertLifecycleEvent.SUPPRESSED

                # Alert exists and is past cooldown - update it
                state.last_seen = current_time
                state.occurrences += 1
                state.correlation_id = candidate.correlation_id
                state.message = candidate.message
                state.cooldown_until = current_time + cooldown_seconds

                return AlertLifecycleEvent.UPDATED
            else:
                # Alert exists but hasn't reached persistence threshold yet
                # Continue tracking occurrences
                state.last_seen = current_time
                state.occurrences += 1
                state.correlation_id = candidate.correlation_id
                state.message = candidate.message

                # Check if we've now reached persistence threshold
                if state.occurrences >= persistence_count:
                    # Alert is now active
                    state.cooldown_until = current_time + cooldown_seconds
                    return AlertLifecycleEvent.CREATED
                else:
                    # Still below threshold
                    return AlertLifecycleEvent.IGNORED

        else:
            # New alert - check if we need to track or create
            # Create a new state to track occurrences
            state = AlertState(
                alert_id=alert_id,
                rule_id=candidate.rule_id,
                source=candidate.source,
                severity=candidate.severity,
                message=candidate.message,
                first_seen=current_time,
                last_seen=current_time,
                occurrences=1,
                acknowledged=False,
                acknowledged_by=None,
                cooldown_until=None,  # Will be set if alert is created
                correlation_id=candidate.correlation_id,
            )

            self._states[alert_id] = state

            # Check if we've reached persistence threshold
            if state.occurrences >= persistence_count:
                # Alert is now active
                state.cooldown_until = current_time + cooldown_seconds
                return AlertLifecycleEvent.CREATED
            else:
                # Still below threshold
                return AlertLifecycleEvent.IGNORED

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

    def get_active_alerts(self) -> list[AlertState]:
        """Get all active alerts.

        Active alerts are those that have reached their persistence threshold
        (i.e., have a cooldown_until set).

        Returns
        -------
        list[AlertState]
            List of all active alert states.
        """
        return [state for state in self._states.values() if state.cooldown_until is not None]
