# sudo apt update && sudo apt upgrade
sudo apt install python3 python3-pip git curl build-essential
sudo apt install openjdk-17-jre
sudo apt install openjdk-17-jdk
curl -sSL https://install.python-poetry.org | python3 -
poetry install && poetry update
# bash ./setup_influxdb.sh
# bash ./setup_kafka.sh
