import sqlite3
from time import sleep

from dt.communication import MQTTClient, MQTTTopics
from dt.sensors import Sensor


class Storage:
    def __init__(self) -> None:
        self.db_path = "plant_dt.db"
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.create_table()

        self.mqtt_client = MQTTClient(id="database")
        self.mqtt_client.connect()

        # Subscribe to the topic where the data is published
        self.mqtt_client.subscribe(MQTTTopics.SOIL_MOISTURE, self.insert_datas)

    def create_table(self) -> None:
        """Create the table to store the data"""
        # I already have a db_init.sql file, so I will use it to create the table
        dir_path = "/".join(__file__.split("/")[:-1])
        with open(f"{dir_path}/db_init.sql", "r") as f:
            self.cursor.executescript(f.read())
            self.conn.commit()
            # print(f.read())

    def insert_data(self, data: dict[str, any]) -> None:
        """Insert read data into the database

        Parameters
        ----------
        data : dict[str, any]
            Data read from a (one) sensor with their metadata

        """
        print(f"I received data: {data}")
        # self.cursor.execute(
        #     "INSERT INTO sensors_data (sensor_id, value, unit, timestamp) VALUES (?, ?, ?, ?)",
        #     (data["sensor_id"], data["value"], data["unit"], data["timestamp"]),
        # )
        # self.conn.commit()

    def insert_datas(self, datas: dict[str, dict[str, any]]) -> None:
        """Insert read data into the database

        Parameters
        ----------
        datas : dict[str, dict[str, any]]
            Data read from the (multiple) sensors with their metadata

        """
        for data in datas.values():
            self.insert_data(data)

    def get_data(self, sensor_id: int, limit: int = 10) -> list[dict[str, any]]:
        """Get the last data read from a sensor

        Parameters
        ----------
        sensor_id : int
            The id of the sensor
        limit : int, optional
            The number of data to retrieve, by default 10

        Returns
        -------
        list[dict[str, any]]
            The last data read from the sensor

        """
        self.cursor.execute(
            "SELECT * FROM sensors_data WHERE sensor_id = ? ORDER BY timestamp DESC LIMIT ?",
            (sensor_id, limit),
        )
        return self.cursor.fetchall()

    def get_sensor_id(self, sensor_name: str) -> int:
        """Get the id of a sensor

        Parameters
        ----------
        sensor_name : str
            The name of the sensor

        Returns
        -------
        int
            The id of the sensor

        """
        self.cursor.execute(
            "SELECT id FROM sensors WHERE name = ?",
            (sensor_name,),
        )
        return self.cursor.fetchone()

    def add_sensor(self, sensor: Sensor) -> None:
        """Add a sensor to the database

        Parameters
        ----------
        sensor : Sensor
            The sensor to add

        """
        self.cursor.execute(
            "INSERT INTO sensors (name) VALUES (?)",
            (sensor.name,),
        )
        self.conn.commit()
        sensor.id = self.cursor.lastrowid  # pyright: ignore[]
        assert sensor.id > 0, "Sensor ID not set"

    def bind_sensors(self, sensor: Sensor) -> None:
        """Bind the sensor to the database

        Parameters
        ----------
        sensor : Sensor
            The sensor to bind

        """
        temp_id = self.get_sensor_id(sensor.name)
        if temp_id:
            sensor.id = temp_id
        else:
            self.add_sensor(sensor)


if __name__ == "__main__":
    storage = Storage()
    while True:
        sleep(1)
