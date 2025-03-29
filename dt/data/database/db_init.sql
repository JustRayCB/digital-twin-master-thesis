CREATE TABLE IF NOT EXISTS sensors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) UNIQUE NOT NULL,
    pin INTEGER NOT NULL,
    read_interval INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sensors_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    value REAL NOT NULL,
    unit VARCHAR(255) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    data_type VARCHAR(255) NOT NULL,
    FOREIGN KEY(sensor_id) REFERENCES sensors(id)
    FOREIGN KEY(data_type) REFERENCES sensors_data_type(name)
);

CREATE TABLE IF NOT EXISTS sensors_data_type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) UNIQUE NOT NULL
);

INSERT OR IGNORE INTO sensors_data_type (name) VALUES 
    ('temperature'), ('soil_moisture'), ('humidity'), ('light_intensity'), ('camera_image')
