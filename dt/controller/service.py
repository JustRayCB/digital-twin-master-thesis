"""Controller Service.

Coordinates routine evaluation, scheduler triggers, and actuator execution.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.controller import (ActionCommand,
                                                     ActionDispatch,
                                                     CompiledRule, ControlMode,
                                                     Routine, RoutineGraph,
                                                     RoutineUpdate)
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import MessagingService
from dt.communication.topics import Topics
from dt.controller.action_keys import build_action_key
from dt.controller.actuator_manager import ActuatorManager
from dt.controller.policies import PolicyManager
from dt.controller.routine_compiler import RoutineCompiler
from dt.controller.routine_evaluator import RoutineEvaluator
from dt.utils import Config, get_logger

logger = get_logger(__name__)


class ControllerService:
    """Controller runtime service."""

    def __init__(
        self,
        database_client: DatabaseApiClient,
        messaging_service: MessagingService,
        policy_manager: PolicyManager,
        actuator_manager: ActuatorManager,
    ):
        self.database_client = database_client
        self.messaging_service = messaging_service
        self.policy_manager = policy_manager
        self.actuator_manager = actuator_manager
        self.compiler = RoutineCompiler()
        self.evaluator = RoutineEvaluator()
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._timezone = ZoneInfo(Config.TIMEZONE)

        self._routine_cache: Dict[int, list[Routine]] = {}
        self._mode_cache: Dict[int, ControlMode] = {}
        self._last_fired: OrderedDict[tuple[int, str], str] = OrderedDict()
        self._sensor_values: OrderedDict[tuple[int, str], float] = OrderedDict()
        self._last_fired_limit = 10_000
        self._sensor_value_limit = 10_000
        self._registered_plants: list[dict[str, Any]] = []
        self._get_registered_plants()

    def get_mode(self, plant_id: int) -> ControlMode:
        if plant_id not in self._mode_cache:
            self._mode_cache[plant_id] = self.database_client.get_mode(plant_id)
        return self._mode_cache[plant_id]

    def set_mode(self, mode: ControlMode) -> ControlMode:
        self.database_client.set_mode(mode)
        self.refresh(mode.plant_id)
        return self.get_mode(mode.plant_id)

    def list_routines(self, plant_id: int) -> list[Routine]:
        return self.database_client.get_routines(plant_id)

    def create_routine(self, payload: RoutineUpdate) -> int:
        if None in (payload.graph, payload.name, payload.plant_id):
            raise ValueError(
                f"Missing required fields (graph, name, plant_id) in payload: {payload}"
            )

        graph = payload.graph
        if not isinstance(graph, RoutineGraph):
            raise ValueError("Invalid graph schema: expected RoutineGraph")
        self._ensure_graph_matches_payload(graph, payload)
        compiled = self.compiler.compile(graph)

        create_payload = RoutineUpdate(
            plant_id=payload.plant_id,
            name=payload.name,
            enabled=payload.enabled if payload.enabled is not None else True,
            graph=payload.graph,
            compiled_rules=compiled,
        )
        routine_id = self.database_client.create_routine(create_payload)
        self.refresh(payload.plant_id)
        return routine_id

    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        if updates.graph is not None:
            if not isinstance(updates.graph, RoutineGraph):
                raise ValueError("Invalid graph schema: expected RoutineGraph")
            self._ensure_graph_matches_payload(updates.graph, updates)
            compiled = self.compiler.compile(updates.graph)
            updates = RoutineUpdate(
                plant_id=updates.plant_id,
                name=updates.name,
                enabled=updates.enabled,
                graph=updates.graph,
                compiled_rules=compiled,
            )
        self.database_client.update_routine(routine_id, updates)
        if updates.plant_id is not None:
            self.refresh(updates.plant_id)
        else:
            self._routine_cache.clear()

    def delete_routine(self, routine_id: int, plant_id: Optional[int] = None) -> None:
        self.database_client.delete_routine(routine_id)
        if plant_id is not None:
            self.refresh(plant_id)
        else:
            self._routine_cache.clear()

    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        return self.database_client.get_action_history(plant_id, limit)

    def start(self) -> None:
        logger.info("Starting Controller Service...")
        if not self.messaging_service.connect():
            logger.error("Failed to connect to Kafka messaging service")
            raise RuntimeError("Failed to connect to Kafka messaging service")
        for topic in Topics.list_sensor_topics():
            if topic == Topics.CAMERA_IMAGE:
                continue
            try:
                processed_topic = (
                    topic.processed if isinstance(topic, Topics) else Topics(topic).processed
                )
                self.messaging_service.subscribe(processed_topic, self.evaluate_routines_for_sensor)
            except Exception as exc:
                logger.error(f"Failed to subscribe to topic {processed_topic}: {exc}")
                raise

        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def stop(self) -> None:
        self._running = False
        self.messaging_service.disconnect()
        if self._scheduler_thread:
            self._scheduler_thread.join()
        logger.info("Controller Service stopped.")

    def _scheduler_loop(self) -> None:
        # Start with last_check set to 1 minute ago to ensure we catch any events that should have fired in the last minute after a restart.
        last_check = self._initial_last_check_time()
        while self._running:
            try:
                now = datetime.now(self._timezone)
                # Ensure we process at least once if time moved forward
                if now <= last_check:
                    time.sleep(0.5)
                    continue

                for plant in self._registered_plants:
                    self.evaluate_time_triggers(plant["id"], last_check, now)

                last_check = now
                time.sleep(1)
            except Exception as exc:
                logger.error(f"Error in scheduler loop: {exc}")
                time.sleep(5)

    def evaluate_routines_for_sensor(self, data: ProcessedSensorData) -> None:
        plant_id = data.plant_id
        now = datetime.now(self._timezone)
        sensor_key = (plant_id, data.topic)
        self._sensor_values[sensor_key] = data.value
        self._sensor_values.move_to_end(sensor_key)
        self._enforce_cache_limits()

        routines = self._get_routines(plant_id)
        for routine in routines:
            compiled = routine.compiled_rules
            if not compiled:
                continue
            for rule in compiled:
                trigger = rule.trigger
                if self.evaluator.trigger_matches(
                    trigger=trigger,
                    topic=data.topic,
                    value=data.value,
                    now=now,
                ):
                    self._execute_rule_actions(routine, rule, correlation_id=data.correlation_id)

    def evaluate_time_triggers(self, plant_id: int, last_check: datetime, now: datetime) -> None:
        # Generate all minute points between last_check (exclusive) and now (inclusive)
        # to ensure we don't skip any scheduled events if the loop lags.
        check_points = self._generate_time_points(last_check, now)
        if not check_points:
            return

        routines = self._get_routines(plant_id)
        for routine in routines:
            compiled = routine.compiled_rules
            if not compiled:
                continue
            created_at = self._parse_created_at(routine.created_at)
            for rule in compiled:
                trigger = rule.trigger
                rule_id = str(rule.id)
                if not rule_id:
                    continue

                for point in check_points:
                    point_time = point.strftime("%H:%M")
                    point_date = point.strftime("%Y-%m-%d")
                    point_key = point.strftime("%Y-%m-%d %H:%M")

                    # Check if already fired for this minute
                    fired_key = (routine.id, rule_id)
                    last_fired = self._last_fired.get(fired_key)
                    if last_fired is not None and last_fired == point_key:
                        continue

                    should_fire = False
                    if trigger.type == "time":
                        if trigger.time == point_time:
                            should_fire = True
                    elif trigger.type == "date":
                        if trigger.date == point_date:
                            if trigger.time:
                                if trigger.time == point_time:
                                    should_fire = True
                            elif point_time == "00:00":
                                should_fire = True
                    elif trigger.type == "interval":
                        if trigger.at == point_time:
                            if self._is_interval_due(created_at, trigger.every_days, point):
                                should_fire = True

                    if should_fire:
                        self._last_fired[fired_key] = point_key
                        self._last_fired.move_to_end(fired_key)
                        self._enforce_cache_limits()
                        # Generate a new unique ID for this specific scheduled event instance
                        trigger_correlation_id = str(uuid.uuid4())
                        self._execute_rule_actions(
                            routine, rule, correlation_id=trigger_correlation_id
                        )

    def _generate_time_points(self, start: datetime, end: datetime) -> list[datetime]:
        """Generate minute-aligned datetime points between start (exclusive) and end (inclusive)."""
        points = []
        # Floor start to minute, then add 1 minute
        current = start.replace(second=0, microsecond=0) + timedelta(minutes=1)

        while current <= end:
            if current > start:  # Strictly greater than start
                points.append(current)
            current += timedelta(minutes=1)

        return points

    def dispatch_action(self, cmd_data: ActionDispatch) -> dict[str, Any]:
        try:
            cmd = self._build_action_command(
                plant_id=cmd_data.plant_id,
                actuator_id=cmd_data.actuator_id,
                command=cmd_data.command,
                duration=float(cmd_data.duration or 0),
                reason=cmd_data.reason or "Manual dispatch",
                source=cmd_data.source or "manual",
                routine_id=None,
                action_id=cmd_data.action_id,
                correlation_id=cmd_data.correlation_id or str(uuid.uuid4()),
            )
            self._execute_action(cmd)
            return {"status": "accepted", "action_id": cmd.action_id}
        except Exception as exc:
            logger.error(f"Dispatch error: {exc}")
            raise ValueError(f"Invalid command data: {exc}") from exc

    def _execute_rule_actions(
        self,
        routine: Routine,
        rule: CompiledRule,
        correlation_id: Optional[str] = None,
    ) -> None:
        commands = self.evaluator.evaluate_actions(
            rule=rule,
            plant_id=routine.plant_id,
            routine_id=routine.id,
            correlation_id=correlation_id,
        )

        for cmd in commands:
            if self._ai_autopilot_enabled(routine.plant_id):
                cmd.status = "skipped"
                cmd.error_message = "Routine suspended while AI auto-pilot mode is enabled"
                self.database_client.log_action_execution(cmd)
                continue
            self._execute_action(cmd)

    def _build_action_command(
        self,
        plant_id: int,
        actuator_id: int,
        command: str,
        duration: float,
        reason: str,
        source: str,
        routine_id: Optional[int],
        action_id: Optional[str],
        correlation_id: str,
    ) -> ActionCommand:
        action_key = action_id or build_action_key(
            source=source,
            plant_id=plant_id,
            actuator_id=actuator_id,
            command=command,
            routine_id=routine_id,
        )
        return ActionCommand(
            plant_id=plant_id,
            action_id=action_key,
            actuator_id=actuator_id,
            timestamp=time.time(),
            duration=duration,
            command=command,
            reason=reason,
            correlation_id=correlation_id,
            source=source,
            routine_id=routine_id,
        )

    def _execute_action(self, command: ActionCommand) -> None:
        self.actuator_manager.execute(command)

    def _ai_autopilot_enabled(self, plant_id: int) -> bool:
        mode = self.get_mode(plant_id)
        return bool(mode.ai_autopilot_enabled)

    def refresh(self, plant_id: int) -> None:
        self._mode_cache[plant_id] = self.database_client.get_mode(plant_id)
        self._routine_cache[plant_id] = self.load_routines(plant_id)

    def _get_routines(self, plant_id: int) -> list[Routine]:
        if plant_id not in self._routine_cache:
            self._routine_cache[plant_id] = self.load_routines(plant_id)
        return self._routine_cache[plant_id]

    def load_routines(self, plant_id: int) -> list[Routine]:
        routines: list[Routine] = []
        for routine in self.database_client.get_routines(plant_id):
            if not routine.enabled:
                continue
            if routine.compiled_rules is None:
                continue
            routines.append(routine)
        return routines

    def _parse_created_at(self, created_at: Any) -> Optional[datetime]:
        if created_at is None:
            return None
        if isinstance(created_at, datetime):
            return created_at
        if isinstance(created_at, str):
            try:
                return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _is_interval_due(
        self, created_at: Optional[datetime], every_days: Optional[int], now: datetime
    ) -> bool:
        if created_at is None or every_days is None or every_days <= 0:
            return False
        created_date = created_at.date()
        current_date = now.date()
        return (current_date - created_date).days % every_days == 0

    def _ensure_graph_matches_payload(self, graph: RoutineGraph, payload: RoutineUpdate) -> None:
        if payload.name is not None and graph.name != payload.name:
            raise ValueError("graph name does not match payload name")
        if payload.plant_id is not None and graph.plant_id != payload.plant_id:
            raise ValueError("graph plant_id does not match payload plant_id")

    def _initial_last_check_time(self) -> datetime:
        return datetime.now(self._timezone) - timedelta(minutes=1)

    def _get_registered_plants(self) -> None:
        self._registered_plants = self.database_client.list_plants()

    def _enforce_cache_limits(self) -> None:
        while len(self._last_fired) > self._last_fired_limit:
            self._last_fired.popitem(last=False)
        while len(self._sensor_values) > self._sensor_value_limit:
            self._sensor_values.popitem(last=False)
