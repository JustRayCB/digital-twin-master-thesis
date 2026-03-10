"""Controller Service Application.

Configures and runs the Controller Service.
"""

from flask import Flask
from flask_cors import CORS

from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService
from dt.controller.actuator_manager import ActuatorManager
from dt.controller.api import create_controller_blueprint
from dt.controller.kinds.fan import Fan
from dt.controller.kinds.heater import Heater
from dt.controller.kinds.light import Light
from dt.controller.kinds.pump import Pump
from dt.controller.policies import PolicyManager
from dt.controller.service import ControllerService
from dt.utils import Config, get_logger

logger = get_logger(__name__)


def _build_actuators(actuator_manager: ActuatorManager) -> None:
    plant_id = 1
    pump = Pump(-1, "pump", plant_id, 24, relay_channel=1)
    light = Light(-1, "light", plant_id, 22, relay_channel=2)
    heater = Heater(-1, "heater", plant_id, 23, relay_channel=3)
    fan = Fan(-1, "fan", plant_id, 27, relay_channel=4)

    actuator_manager.add_actuator(pump)
    actuator_manager.add_actuator(light)
    actuator_manager.add_actuator(heater)
    actuator_manager.add_actuator(fan)


def create_app(config=Config, service=None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)

    app.config["DT_CONFIG"] = config

    if service is None:
        policy_manager = PolicyManager()
        database_client = DatabaseApiClient(base_url=config.FLASK_DB_URL)
        messaging_service = KafkaService(
            host=config.KAFKA_URL,
            client_id="controller_service",
            group_id="controller_group",
        )
        actuator_manager = ActuatorManager(
            actuators={},
            policy_manager=policy_manager,
            messaging_service=messaging_service,
            database_client=database_client,
        )
        _build_actuators(actuator_manager)
        service = ControllerService(
            database_client=database_client,
            messaging_service=messaging_service,
            policy_manager=policy_manager,
            actuator_manager=actuator_manager,
        )

    app.service = service  # type: ignore

    bp = create_controller_blueprint(service)
    app.register_blueprint(bp)

    return app


if __name__ == "__main__":
    import os

    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = Config.DEBUG_MODE.value == "True"

    policy_manager = PolicyManager()
    database_client = DatabaseApiClient(base_url=Config.FLASK_DB_URL)
    messaging_service = KafkaService(
        host=Config.KAFKA_URL,
        client_id="controller_service",
        group_id="controller_group",
    )
    actuator_manager = ActuatorManager(
        actuators={},
        policy_manager=policy_manager,
        messaging_service=messaging_service,
        database_client=database_client,
    )
    _build_actuators(actuator_manager)
    service = ControllerService(
        database_client=database_client,
        messaging_service=messaging_service,
        policy_manager=policy_manager,
        actuator_manager=actuator_manager,
    )

    app = create_app(config=Config, service=service)

    if not debug_mode or in_reloader:
        try:
            service.start()
        except Exception as exc:
            logger.error(f"Failed to start controller service: {exc}")

    try:
        app.run(host="0.0.0.0", port=5004, debug=debug_mode)
    finally:
        if not debug_mode or in_reloader:
            service.stop()
