"""Alert Engine Service.

This module provides a centralized alert engine that:
- Evaluates configured alert rules against processed sensor readings
- Exposes REST API for alert submission, acknowledgment, and clearing
- Maintains in-memory alert state (deduplication, persistence, cooldown)
- Publishes canonical alert events to Kafka for downstream consumers

TODO: Implement alert engine service following TDD approach.
"""

from dt.alerts.app import create_app

__all__ = ["create_app"]
