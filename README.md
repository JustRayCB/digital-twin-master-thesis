# digital-twin-plant

This thesis focuses on implementing a Digital Twin integrated in an Internet of Things stack to monitor plant health. Sensors feed data to a Raspberry Pi acting as the edge controller, while supporting services (Kafka, InfluxDB, Spark) provide messaging, storage, and analytics.

## Automated Setup Scripts

These helper scripts assume a fresh Debian/Ubuntu machine with sudo privileges and an active internet connection. Make them executable with `chmod +x <script>` before running.

### Base System Provisioning — `scripts/setup.sh`

```
bash scripts/setup.sh
```
What it does:
- Installs core tooling (`python3`, `python3-pip`, `git`, `curl`, `build-essential`).
- Installs OpenJDK 17 (JRE + JDK) required by Spark and Kafka.
- Installs Poetry via the official installer, then runs `poetry install && poetry update` inside the repository.

Good to know:
- The script targets apt-based distributions; it will prompt for your sudo password.
- Run `sudo apt update && sudo apt upgrade` first on unpatched systems.
- Adjust the Poetry environment afterwards with one of the Makefile profiles if you need a specific runtime.
- The script will install Poetry for your user; open a new shell or source `$HOME/.poetry/env` if Poetry is not immediately on your PATH.

### Kafka Node Provisioning — `scripts/setup_kafka.sh`

```
bash scripts/setup_kafka.sh
```
What it does:
- Updates apt packages and installs `default-jdk`, `net-tools`, `jq`, `netcat-traditional`, plus `wget` if missing.
- Downloads Apache Kafka 4.0.0 (Scala 2.13) into `/opt/kafka` and creates the log directory `/var/kafka-logs`.
- Creates a system user `kafka`, adjusts ownership, and adds your account to the `kafka` group.
- Detects local/public IPs, generates a cluster ID, writes a KRaft `server.properties`, and formats storage.
- Installs and enables a `kafka-kraft.service` systemd unit with a 512 MB heap, then waits for the broker to listen on `9092`.

Good to know:
- The script aborts if `/opt/kafka` already exists—remove or back up an existing install before rerunning.
- It queries `curl -4 ifconfig.me` to discover the public IP; set `PUBLIC_IP` manually if the host has no internet-facing address or sits behind NAT.
- Log out/in after the script so your shell picks up membership in the `kafka` group.
- Check status with `sudo systemctl status kafka-kraft.service`; inspect logs via `journalctl -u kafka-kraft.service`.
- External clients can reach the broker on `PLAINTEXT://<public-ip>:19092` by default.

### InfluxDB Provisioning — `scripts/setup_influxdb.sh`

```
bash scripts/setup_influxdb.sh
```
What it does:
- Downloads and verifies the InfluxData apt repository GPG key, then configures the repository.
- Installs `influxdb2`, enables the `influxdb` systemd service, and starts it immediately.

Good to know:
- Complete the initial onboarding (`influx setup` or the web UI at http://localhost:8086) to create an org, bucket, and API token.
- Adjust the repository URL for non-Debian derivatives if necessary.
- Confirm status with `sudo systemctl status influxdb` and logs via `journalctl -u influxdb`.

## Manual Raspberry Pi Checklist

If you prefer to provision manually (e.g., before running the scripts):
- Flash Raspberry Pi OS Lite (64-bit) with Raspberry Pi Imager.
- Boot and run `sudo apt update && sudo apt upgrade`.
- Install base packages (`sudo apt install python3 python3-pip git curl build-essential`).
- Run `sudo raspi-config` to enable auto-login, SSH, I2C, one-wire, and Remote GPIO.
- Install Java 17 (`sudo apt install openjdk-17-jdk`).
- Clone this repository and install dependencies via Poetry (e.g., `poetry install --extras "raspi spark" --no-root`) or the Makefile profiles below.
- Execute the Kafka and InfluxDB setup scripts if the Pi will host those services.

## Dependencies Overview

- **Kafka**: Provision with `bash scripts/setup_kafka.sh`; broker listens on `9092` internally and `19092` for external clients.
- **InfluxDB 2.x**: Provision with `bash scripts/setup_influxdb.sh`; UI/API available on `http://localhost:8086`.
- **Apache Spark**: Requires Java 17; install via the Poetry profiles that include the `spark` extras.

## Installation Profiles (Poetry / Makefile)

Use `poetry install --with …` directly or rely on the Makefile helpers:
- **dev**: `make install-dev` → core + `dev`, `db`, `spark` extras (laptop development).
- **rpi**: `make install-rpi` → lean runtime for Raspberry Pi (`main`, `rpi`, `db`).
- **db**: `make install-db` → services focused node (`main`, `db`).
- **spark**: `make install-spark` → analytics node with Spark extras (`main`, `spark`).
- **naked**: `make install-naked` → minimal `main` dependencies only.

Pick the profile that matches the machine’s role; you can rerun with a different target later if the node’s responsibilities change.

## Next Steps

- Use `make run-dashboard`, `make run-collector`, `make run-controller`, or `make run-database` to start individual components.
- Run `make test` to validate the codebase with pytest.
- Refer to `scripts/kafka_manager.py` for additional Kafka management utilities once the broker is running.
