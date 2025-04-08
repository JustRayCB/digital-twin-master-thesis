"""
kafka_manager.py - A utility script to manage Kafka topics in KRaft mode.
Usage:
  python3 kafka_manager.py <command> [options]

Commands:
  create <topic> --partitions <num> --replication-factor <num> [--config <key=value>]
  delete <topic>
  list
  describe <topic>
  alter <topic> --partitions <num> [--config <key=value>]
  config [--add <key=value>] [--delete <key>] <topic>

Examples:
  python3 kafka_manager.py create sensor-data --partitions 3 --replication-factor 1
  python3 kafka_manager.py list
  python3 kafka_manager.py delete sensor-data
  python3 kafka_manager.py describe plant-moisture
  python3 kafka_manager.py alter plant-moisture --partitions 5
  python3 kafka_manager.py config --add retention.ms=86400000 plant-moisture
"""

import argparse
import json
import os
import subprocess
import sys

from dt.communication import Topics

# Configuration
KAFKA_DIR = "/opt/kafka"  # Match your installation directory
KAFKA_BOOTSTRAP_SERVER = "localhost:9092"


class KafkaManager:
    def __init__(self):
        self.kafka_dir = KAFKA_DIR
        self.bootstrap_server = KAFKA_BOOTSTRAP_SERVER

    def run_command(self, command):
        """Execute a shell command and return its output"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {e.stderr.strip()}")
            sys.exit(1)

    def create_topic(self, topic_name, partitions, replication_factor, config=None):
        """Create a new Kafka topic"""
        cmd = (
            f"{self.kafka_dir}/bin/kafka-topics.sh --bootstrap-server {self.bootstrap_server} "
            f"--create --topic {topic_name} --partitions {partitions} "
            f"--replication-factor {replication_factor}"
        )

        if config:
            config_str = " ".join([f"--config {k}={v}" for k, v in config.items()])
            cmd += f" {config_str}"

        output = self.run_command(cmd)
        print(f"Topic '{topic_name}' created successfully.")
        return output

    def delete_topic(self, topic_name):
        """Delete a Kafka topic"""
        cmd = (
            f"{self.kafka_dir}/bin/kafka-topics.sh --bootstrap-server {self.bootstrap_server} "
            f"--delete --topic {topic_name}"
        )

        output = self.run_command(cmd)
        print(f"Topic '{topic_name}' marked for deletion.")
        print("Note: Topic deletion may take some time to complete.")
        return output

    def list_topics(self):
        """List all available Kafka topics"""
        cmd = (
            f"{self.kafka_dir}/bin/kafka-topics.sh --bootstrap-server {self.bootstrap_server} "
            f"--list"
        )

        output = self.run_command(cmd)
        topics = output.strip().split("\n")

        if not topics or (len(topics) == 1 and not topics[0]):
            print("No topics found.")
            return []

        print("Available Topics:")
        for topic in topics:
            if topic:  # Skip empty lines
                print(f"- {topic}")

        return topics

    def describe_topic(self, topic_name):
        """Describe a Kafka topic"""
        cmd = (
            f"{self.kafka_dir}/bin/kafka-topics.sh --bootstrap-server {self.bootstrap_server} "
            f"--describe --topic {topic_name}"
        )

        output = self.run_command(cmd)
        print(f"Topic Description for '{topic_name}':")
        print(output)
        return output

    def alter_topic(self, topic_name, partitions=None, config=None):
        """Alter a Kafka topic's configuration or partition count.

        Parameters
        ----------
        topic_name : str
            Name of the topic to alter.
        partitions : int, optional
            Number of partitions to set for the topic.
        config : dict, optional
            Dictionary of configuration options to set. (e.g., retention.ms, cleanup.policy, ...)

        Returns
        -------
        str
            The output of the command execution.

        """
        cmd = (
            f"{self.kafka_dir}/bin/kafka-topics.sh --bootstrap-server {self.bootstrap_server} "
            f"--alter --topic {topic_name}"
        )

        if partitions:
            cmd += f" --partitions {partitions}"

        if config:
            config_str = " ".join([f"--config {k}={v}" for k, v in config.items()])
            cmd += f" {config_str}"

        output = self.run_command(cmd)
        print(f"Topic '{topic_name}' altered successfully.")
        return output

    def modify_config(self, topic_name, add_config=None, delete_config=None):
        """Modify topic configuration for a Kafka topic.
        This can be used to add or delete configuration options.
        - retention.ms: How long messages should be kept before being deleted (milliseconds).
        - cleanup.policy: The policy for cleaning up old segment (e.g., delete, compact).
        - max.message.bytes: Maximum size of a message (bytes).
        - segment.bytes: Size of a segment file (bytes).

        Parameters
        ----------
        topic_name : str
            Name of the topic to modify.
        add_config : dict, optional
            Dictionary of configuration options to add or modify.
        delete_config : list, optional
            List of configuration keys to delete.

        Returns
        -------
        str
            Output of the command execution.
        """
        cmd = (
            f"{self.kafka_dir}/bin/kafka-configs.sh --bootstrap-server {self.bootstrap_server} "
            f"--entity-type topics --entity-name {topic_name}"
        )

        if add_config:
            config_str = ",".join([f"{k}={v}" for k, v in add_config.items()])
            cmd += f" --alter --add-config {config_str}"

        if delete_config:
            config_str = ",".join(delete_config)
            cmd += f" --alter --delete-config {config_str}"

        output = self.run_command(cmd)
        print(f"Configuration for topic '{topic_name}' updated successfully.")
        return output

    def setup_kafka(self):
        """Setup Kafka with default topics and configurations"""
        for topic in Topics.list_topics():
            self.create_topic(topic_name=topic.raw, partitions=2, replication_factor=1)
            self.create_topic(topic_name=topic.processed, partitions=2, replication_factor=1)
        self.create_topic(topic_name="alerts", partitions=1, replication_factor=1)
        self.create_topic(topic_name="commands", partitions=1, replication_factor=1)
        self.create_topic(topic_name="commands-response", partitions=1, replication_factor=1)
        self.create_topic(topic_name="health-status", partitions=1, replication_factor=1)


def parse_config_option(config_str):
    """Parse key=value config options into a dictionary"""
    if not config_str:
        return {}

    config_dict = {}
    for item in config_str:
        if "=" in item:
            key, value = item.split("=", 1)
            config_dict[key.strip()] = value.strip()
        else:
            print(
                f"Warning: Ignoring malformed config option '{item}'. Format should be key=value."
            )

    return config_dict


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Kafka Topic Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create topic command
    create_parser = subparsers.add_parser("create", help="Create a new topic")
    create_parser.add_argument("topic", help="Topic name")
    create_parser.add_argument("--partitions", type=int, required=True, help="Number of partitions")
    create_parser.add_argument(
        "--replication-factor", type=int, required=True, help="Replication factor"
    )
    create_parser.add_argument("--config", nargs="+", help="Configuration in format key=value")

    # Delete topic command
    delete_parser = subparsers.add_parser("delete", help="Delete a topic")
    delete_parser.add_argument("topic", help="Topic name")

    # List topics command
    subparsers.add_parser("list", help="List all topics")

    # Describe topic command
    describe_parser = subparsers.add_parser("describe", help="Describe a topic")
    describe_parser.add_argument("topic", help="Topic name")

    # Alter topic command
    alter_parser = subparsers.add_parser("alter", help="Alter a topic")
    alter_parser.add_argument("topic", help="Topic name")
    alter_parser.add_argument("--partitions", type=int, help="New partition count")
    alter_parser.add_argument("--config", nargs="+", help="Configuration in format key=value")

    # Config topic command
    config_parser = subparsers.add_parser("config", help="Modify topic configuration")
    config_parser.add_argument("topic", help="Topic name")
    config_parser.add_argument("--add", nargs="+", help="Add configuration in format key=value")
    config_parser.add_argument("--delete", nargs="+", help="Delete configuration keys")

    conifg_parser = subparsers.add_parser("setup", help="Setup Kafka")

    return parser.parse_args()


def main():
    """Main entry point for the script"""
    args = parse_arguments()
    manager = KafkaManager()

    if not args.command:
        print("Error: No command specified.")
        print(__doc__)
        sys.exit(1)

    if args.command == "create":
        config = parse_config_option(args.config) if args.config else None
        manager.create_topic(args.topic, args.partitions, args.replication_factor, config)

    elif args.command == "delete":
        manager.delete_topic(args.topic)

    elif args.command == "list":
        manager.list_topics()

    elif args.command == "describe":
        manager.describe_topic(args.topic)

    elif args.command == "alter":
        config = parse_config_option(args.config) if args.config else None
        manager.alter_topic(args.topic, args.partitions, config)

    elif args.command == "config":
        add_config = parse_config_option(args.add) if args.add else None
        delete_config = args.delete if args.delete else None
        manager.modify_config(args.topic, add_config, delete_config)

    elif args.command == "setup":
        # Setup Kafka with default topics
        manager.setup_kafka()
        print("Kafka setup completed with default topics.")


if __name__ == "__main__":
    main()
