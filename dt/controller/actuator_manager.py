"""Actuator manager for execution and policy enforcement."""

import threading
import time
from typing import Dict

from dt.communication.dataclasses.controller import (ActionCommand,
                                                     ActuatorConfig)
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import MessagingService
from dt.communication.topics import Topics
from dt.controller.action_keys import build_action_key
from dt.controller.kinds.base_actuator import BaseActuator
from dt.controller.policies import PolicyManager
from dt.utils import get_logger


class ActuatorManager:
    """Executes actions on actuators while enforcing safety policies."""

    def __init__(
        self,
        actuators: Dict[int, BaseActuator],
        policy_manager: PolicyManager,
        messaging_service: MessagingService,
        database_client: DatabaseApiClient,
    ):
        self.actuators = actuators
        self.policy_manager = policy_manager
        self.messaging_service = messaging_service
        self.database_client = database_client
        self.lock = threading.Lock()
        self.active_executions: Dict[int, Dict[str, float]] = {}
        self.last_completed: Dict[int, float] = {}
        self.logger = get_logger(__name__)

    def add_actuator(self, actuator: BaseActuator):
        actuator_id = self.bind_actuator(actuator)
        self.actuators[actuator_id] = actuator
        self.logger.info(f"Added actuator {actuator.name} with ID {actuator_id}")

    def bind_actuator(self, actuator: BaseActuator) -> int:
        self.logger.info(f"Binding actuator {actuator.name} to database")
        actuator_id = self.database_client.bind_actuator(
            plant_id=actuator.plant_id,
            name=actuator.name,
            pin=actuator.pin,
            relay_channel=actuator.relay_channel,
        )
        if actuator_id != -1:
            actuator.actuator_id = actuator_id
            self.logger.info(f"Actuator {actuator.name} bound with ID {actuator_id} successfully")
        else:
            self.logger.error(f"Failed to bind actuator {actuator.name} to database: {actuator_id}")
            # TODO: Define a specific exception for this case
            raise Exception(f"Failed to bind actuator {actuator.name} to database: {actuator_id}")

        return actuator_id

    def execute(self, action: ActionCommand) -> bool:
        self.logger.info(f"Received action: {action}")
        action.status = "running"
        self._log_action(action)

        actuator = self.actuators.get(action.actuator_id)
        if not actuator:
            self._reject(action, "Actuator not found")
            return False

        policy = self.policy_manager.resolve(action.plant_id, actuator.name)
        if not self._validate_policy(action, policy):
            return False

        with self.lock:
            if action.actuator_id in self.active_executions:
                if action.command.upper() != "OFF" and not policy.allow_overlap:
                    self._reject(action, "Actuator busy (overlap not allowed)")
                    return False

            self.active_executions[action.actuator_id] = {"start_time": time.time()}

        try:
            success = actuator.execute(action.command)
            if success:
                if action.command.upper() == "ON" and action.duration > 0:
                    self._schedule_auto_off(action)
                else:
                    self._complete(action)
            else:
                self._fail(action, "Hardware execution failed")
            return success
        except Exception as exc:
            self._fail(action, f"Exception during execution: {exc}")
            return False

    def _schedule_auto_off(self, original_action: ActionCommand) -> None:
        timer = threading.Timer(original_action.duration, self._auto_off, args=[original_action])
        timer.start()

    def _auto_off(self, original_action: ActionCommand) -> None:
        self.logger.info(f"Auto-off timer for action {original_action.action_id}")
        off_action = ActionCommand(
            plant_id=original_action.plant_id,
            action_id=build_action_key(
                source=original_action.source,
                plant_id=original_action.plant_id,
                actuator_id=original_action.actuator_id,
                command="OFF",
                routine_id=original_action.routine_id,
            ),
            actuator_id=original_action.actuator_id,
            started_at=time.time(),
            duration=0,
            command="OFF",
            reason="Auto-off timer",
            correlation_id=original_action.correlation_id,
            source=original_action.source,
            routine_id=original_action.routine_id,
        )
        success = self.execute(off_action)
        if success:
            original_action.status = "completed"
            self._log_action(original_action)
        else:
            original_action.status = "failed"
            original_action.error_message = "Auto-off execution failed"
            self._log_action(original_action)

    def _validate_policy(self, action: ActionCommand, policy: ActuatorConfig) -> bool:
        # Always allow OFF commands to ensure we can stop actuators if needed
        if action.command.upper() == "OFF":
            return True

        if policy.allowed_commands and action.command.upper() not in policy.allowed_commands:
            self._reject(action, f"Command {action.command} not allowed by policy")
            return False

        if (
            policy.max_duration_seconds is not None
            and action.duration > policy.max_duration_seconds
        ):
            self._reject(
                action, f"Duration {action.duration} exceeds max {policy.max_duration_seconds}"
            )
            return False

        if policy.min_cooldown_seconds is not None:
            last_end = self.last_completed.get(action.actuator_id)
            if last_end is not None and (time.time() - last_end) < policy.min_cooldown_seconds:
                self._reject(action, "Cooldown active for actuator")
                return False

        return True

    def _reject(self, action: ActionCommand, reason: str) -> None:
        self.logger.warning(f"Action {action.action_id} REJECTED: {reason}")
        action.status = "rejected"
        action.error_message = reason
        self._log_action(action)

    def _complete(self, action: ActionCommand) -> None:
        self.logger.info(f"Action {action.action_id} COMPLETED")
        action.status = "completed"
        self._log_action(action)
        with self.lock:
            self.active_executions.pop(action.actuator_id, None)
            self.last_completed[action.actuator_id] = time.time()

    def _fail(self, action: ActionCommand, reason: str) -> None:
        self.logger.error(f"Action {action.action_id} FAILED: {reason}")
        action.status = "failed"
        action.error_message = reason
        self._log_action(action)
        with self.lock:
            self.active_executions.pop(action.actuator_id, None)

    def _log_action(self, action: ActionCommand) -> None:
        if not self.messaging_service.publish(Topics.ACTIONS, action):
            self.logger.warning(f"Failed to publish action status for {action.action_id}")
