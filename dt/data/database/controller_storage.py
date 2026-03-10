from sqlalchemy import text
from abc import ABC, abstractmethod

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.controller import ActionCommand, ControlMode, Routine, RoutineUpdate
from dt.data.database.base_storage import DatabaseStorage


class ControllerStorage(DatabaseStorage, ABC):
    """Storage capability for controller state and action history."""

    @abstractmethod
    def get_mode(self, plant_id: int) -> ControlMode:
        """Get the current control mode for a plant.

        Parameters
        ----------
        plant_id : int
            The ID of the plant.

        Returns
        -------
        ControlMode
            The control mode configuration.
        """
        ...

    @abstractmethod
    def set_mode(self, mode: ControlMode) -> None:
        """Set the control mode for a plant.

        Parameters
        ----------
        mode : ControlMode
            Updated control mode configuration.
        """
        ...

    @abstractmethod
    def get_routines(self, plant_id: int) -> list[Routine]:
        """Get all routines for a plant.

        Parameters
        ----------
        plant_id : int
            The ID of the plant.

        Returns
        -------
        list[Routine]
            List of routines.
        """
        ...

    @abstractmethod
    def create_routine(self, routine: RoutineUpdate) -> int:
        """Create a new routine.

        Parameters
        ----------
        routine : RoutineUpdate
            The routine data including compiled rules.
        Returns
        -------
        int
            The ID of the newly created routine.
        """
        ...

    @abstractmethod
    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        """Update a routine.

        Parameters
        ----------
        routine_id : int
            The ID of the routine to update.
        updates : RoutineUpdate
            The fields to update.
        """
        ...

    @abstractmethod
    def delete_routine(self, routine_id: int) -> None:
        """Delete a routine.

        Parameters
        ----------
        routine_id : int
            The ID of the routine to delete.
        """
        ...

    @abstractmethod
    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        """Get action execution history for a plant.

        Parameters
        ----------
        plant_id : int
            The ID of the plant.
        limit : int, optional
            Maximum number of records to return, by default 50.

        Returns
        -------
        list[ActionCommand]
            List of action execution records.
        """
        ...

    @abstractmethod
    def log_action_execution(self, action: ActionCommand) -> None:
        """Log an action execution event.

        Parameters
        ----------
        action : ActionCommand
            The action command.
        """
        ...

class ControllerStore(ControllerStorage):
    """Persistence for controller state, routines, and action history events."""

    def get_mode(self, plant_id: int) -> ControlMode:
        query = "SELECT * FROM controller_modes WHERE plant_id = :plant_id"
        with self._get_connection() as conn:
            result = conn.execute(text(query), {"plant_id": plant_id}).fetchone()
            if result:
                return load("db_row", ControlMode, result)
            return ControlMode(plant_id, False, "routine")

    def set_mode(self, mode: ControlMode) -> None:
        query = """
            INSERT INTO controller_modes (plant_id, ai_autopilot_enabled, owner, updated_at)
            VALUES (:plant_id, :ai_autopilot_enabled, :owner, COALESCE(:updated_at, NOW()))
            ON CONFLICT (plant_id) DO UPDATE
            SET ai_autopilot_enabled = EXCLUDED.ai_autopilot_enabled,
                owner = EXCLUDED.owner,
                updated_at = EXCLUDED.updated_at
        """
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", mode))

    def get_routines(self, plant_id: int) -> list[Routine]:
        query = "SELECT * FROM routines WHERE plant_id = :plant_id ORDER BY id"
        with self._get_connection() as conn:
            result = conn.execute(text(query), {"plant_id": plant_id}).fetchall()
            return [load("db_row", Routine, row) for row in result]

    def create_routine(self, routine: RoutineUpdate) -> int:
        query = """
            INSERT INTO routines (plant_id, name, enabled, graph, compiled_rules)
            VALUES (:plant_id, :name, :enabled, :graph, :compiled_rules)
            RETURNING id
        """
        params = dump("db_row", routine)
        if params.get("compiled_rules") is None:
            raise ValueError("compiled_rules is required to create a routine")
        with self._get_connection() as conn:
            new_id = self._get_id(conn.execute(text(query), params))
            self.logger.info(f"Created routine {new_id} for plant {routine.plant_id}")
            return new_id

    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        fields = []
        params = {"id": routine_id}
        updates_data = dump("db_row", updates)
        allowed_fields = {"plant_id", "name", "enabled", "graph", "compiled_rules"}
        for key, value in updates_data.items():
            if value is None:
                continue
            if key in allowed_fields:
                fields.append(f"{key} = :{key}")
                params[key] = value

        if not fields:
            return

        query = f"UPDATE routines SET {', '.join(fields)}, updated_at = NOW() WHERE id = :id"
        with self._get_connection() as conn:
            conn.execute(text(query), params)
            self.logger.info(f"Updated routine {routine_id}")

    def delete_routine(self, routine_id: int) -> None:
        query = "DELETE FROM routines WHERE id = :id"
        with self._get_connection() as conn:
            conn.execute(text(query), {"id": routine_id})
            self.logger.info(f"Deleted routine {routine_id}")

    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        query = """
            SELECT * FROM action_executions
            WHERE plant_id = :plant_id
            ORDER BY event_at DESC, id DESC
            LIMIT :limit
        """
        with self._get_connection() as conn:
            result = conn.execute(text(query), {"plant_id": plant_id, "limit": limit}).fetchall()
            return [load("db_row", ActionCommand, row) for row in result]

    def log_action_execution(self, action: ActionCommand) -> None:
        query = """
            INSERT INTO action_executions (
                execution_id, action_id, plant_id, actuator_id, routine_id, source, command,
                duration, reason, status, error_message, correlation_id, event_at
            ) VALUES (
                :execution_id, :action_id, :plant_id, :actuator_id, :routine_id, :source,
                :command, :duration, :reason, :status, :error_message, :correlation_id,
                to_timestamp(:event_at)
            )
        """
        if action.status is None:
            raise ValueError("ActionCommand.status is required to log execution")
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", action))
