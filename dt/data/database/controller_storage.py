from sqlalchemy import text
from abc import ABC, abstractmethod

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.controller import (ActionCommand,
                                                     ActuatorConfigSet,
                                                     ControlMode, Routine,
                                                     RoutineUpdate)
from dt.communication.dataclasses.queries import ActionHistoryQuery
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
    def get_action_history(self, query: ActionHistoryQuery) -> list[ActionCommand]:
        """Get action execution history for a plant.

        Parameters
        ----------
        query : ActionHistoryQuery
            Query parameters including plant, optional bounds, and limit.

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

    @abstractmethod
    def get_policies(self) -> ActuatorConfigSet:
        """Get the actuator policies from the database.

        Returns
        -------
        ActuatorConfigSet
            The actuator policy configuration.
        """
        ...

    @abstractmethod
    def set_policies(self, policies: ActuatorConfigSet) -> None:
        """Set the actuator policies in the database.

        Parameters
        ----------
        policies : ActuatorConfigSet
            The actuator policy configuration to persist.
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

    def get_action_history(self, query_data: ActionHistoryQuery) -> list[ActionCommand]:
        filters = ["plant_id = :plant_id"]
        params: dict[str, int | float] = {"plant_id": query_data.plant_id}
        if query_data.since is not None:
            filters.append("event_at >= to_timestamp(:since)")
            params["since"] = query_data.since
        if query_data.until is not None:
            filters.append("event_at <= to_timestamp(:until)")
            params["until"] = query_data.until

        limit_clause = " LIMIT :limit" if query_data.effective_limit is not None else ""
        if query_data.effective_limit is not None:
            params["limit"] = query_data.effective_limit

        query = """
            SELECT * FROM action_executions
            WHERE {filters}
            ORDER BY event_at DESC, id DESC
            {limit_clause}
        """.format(filters=" AND ".join(filters), limit_clause=limit_clause)
        with self._get_connection() as conn:
            result = conn.execute(text(query), params).fetchall()
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

    def get_policies(self) -> ActuatorConfigSet:
        query = "SELECT * FROM actuator_policies"
        with self._get_connection() as conn:
            results = conn.execute(text(query)).fetchall()

        return load("db_row", ActuatorConfigSet, results)

    def set_policies(self, policies: ActuatorConfigSet) -> None:
        # First clear existing policies
        delete_query = "DELETE FROM actuator_policies"

        insert_query = """
            INSERT INTO actuator_policies (
                plant_id, actuator_name, max_duration_seconds, min_cooldown_seconds,
                allow_overlap, allowed_commands, updated_at
            ) VALUES (
                :plant_id, :actuator_name, :max_duration_seconds, :min_cooldown_seconds,
                :allow_overlap, :allowed_commands, NOW()
            )
        """

        with self._get_connection() as conn:
            conn.execute(text(delete_query))

            # Insert defaults
            conn.execute(text(insert_query), {
                "plant_id": None,
                "actuator_name": None,
                "max_duration_seconds": policies.defaults.max_duration_seconds,
                "min_cooldown_seconds": policies.defaults.min_cooldown_seconds,
                "allow_overlap": policies.defaults.allow_overlap,
                "allowed_commands": policies.defaults.allowed_commands
            })

            # Insert global actuators
            for name, config in policies.actuators.items():
                conn.execute(text(insert_query), {
                    "plant_id": None,
                    "actuator_name": name,
                    "max_duration_seconds": config.max_duration_seconds,
                    "min_cooldown_seconds": config.min_cooldown_seconds,
                    "allow_overlap": config.allow_overlap,
                    "allowed_commands": config.allowed_commands
                })

            # Insert plant-specific overrides
            for plant_id_str, plant_config in policies.plants.items():
                try:
                    plant_id = int(plant_id_str)
                except ValueError:
                    continue

                for name, config in plant_config.actuators.items():
                    conn.execute(text(insert_query), {
                        "plant_id": plant_id,
                        "actuator_name": name,
                        "max_duration_seconds": config.max_duration_seconds,
                        "min_cooldown_seconds": config.min_cooldown_seconds,
                        "allow_overlap": config.allow_overlap,
                        "allowed_commands": config.allowed_commands
                    })
