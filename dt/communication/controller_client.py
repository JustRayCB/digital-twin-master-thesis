"""HTTP client for the controller service.

Provides a thin wrapper over the Flask controller API for managing modes,
routines, and dispatching actions.
"""

from typing import Any, List, Optional
import requests

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.controller import (
    ActionDispatch,
    ActionCommand,
    ControlMode,
    Routine,
    RoutineCreate,
    RoutineUpdate,
)
from dt.utils import Config, get_logger


class ControllerClient:
    """Client for interacting with the controller service HTTP API."""

    def __init__(self, base_url: str = Config.FLASK_CONTROLLER_URL):
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger(__name__)

    # ---------------------------------------------------------------------- #
    # Mode
    # ---------------------------------------------------------------------- #
    def get_mode(self, plant_id: int) -> ControlMode:
        """Get the current control mode for a plant."""
        try:
            response = requests.get(
                f"{self.base_url}/controller/mode",
                params={"plant_id": plant_id},
                timeout=5,
            )
            response.raise_for_status()
            return load("generic", ControlMode, response.json())
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching controller mode: {exc}")
            raise RuntimeError(f"Failed to fetch controller mode: {exc}") from exc

    def set_mode(self, plant_id: int, ai_autopilot_enabled: bool, owner: str) -> ControlMode:
        """Set the control mode for a plant."""
        payload = {
            "plant_id": plant_id,
            "ai_autopilot_enabled": ai_autopilot_enabled,
            "owner": owner,
        }
        try:
            response = requests.put(
                f"{self.base_url}/controller/mode",
                json=payload,
                timeout=5,
            )
            response.raise_for_status()
            # The API returns {"status": "updated", "mode": {...}}
            return load("generic", ControlMode, response.json()["mode"])
        except requests.RequestException as exc:
            self.logger.error(f"Error setting controller mode: {exc}")
            raise RuntimeError(f"Failed to set controller mode: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Routines
    # ---------------------------------------------------------------------- #
    def list_routines(self, plant_id: int) -> List[Routine]:
        """List all routines for a plant."""
        try:
            response = requests.get(
                f"{self.base_url}/controller/routines",
                params={"plant_id": plant_id},
                timeout=5,
            )
            response.raise_for_status()
            return [load("generic", Routine, item) for item in response.json()]
        except requests.RequestException as exc:
            self.logger.error(f"Error listing routines: {exc}")
            raise RuntimeError(f"Failed to list routines: {exc}") from exc

    def create_routine(self, routine: RoutineCreate) -> int:
        """Create a new routine. Returns the ID."""
        try:
            response = requests.post(
                f"{self.base_url}/controller/routines",
                json=dump("generic", routine),
                timeout=5,
            )
            response.raise_for_status()
            return int(response.json()["id"])
        except requests.RequestException as exc:
            self.logger.error(f"Error creating routine: {exc}")
            raise RuntimeError(f"Failed to create routine: {exc}") from exc

    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        """Update an existing routine."""
        try:
            response = requests.put(
                f"{self.base_url}/controller/routines/{routine_id}",
                json=dump("generic", updates),
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error updating routine: {exc}")
            raise RuntimeError(f"Failed to update routine: {exc}") from exc

    def delete_routine(self, routine_id: int) -> None:
        """Delete a routine."""
        try:
            response = requests.delete(
                f"{self.base_url}/controller/routines/{routine_id}",
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error deleting routine: {exc}")
            raise RuntimeError(f"Failed to delete routine: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Actions
    # ---------------------------------------------------------------------- #
    def dispatch_action(self, command: ActionDispatch) -> dict[str, Any]:
        """Dispatch a manual or AI action."""
        try:
            response = requests.post(
                f"{self.base_url}/controller/actions/dispatch",
                json=dump("generic", command),
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error(f"Error dispatching action: {exc}")
            raise RuntimeError(f"Failed to dispatch action: {exc}") from exc

    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        """Get action execution history."""
        try:
            response = requests.get(
                f"{self.base_url}/controller/actions/history",
                params={"plant_id": plant_id, "limit": limit},
                timeout=5,
            )
            response.raise_for_status()
            return [load("generic", ActionCommand, item) for item in response.json()]
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching action history: {exc}")
            raise RuntimeError(f"Failed to fetch action history: {exc}") from exc
