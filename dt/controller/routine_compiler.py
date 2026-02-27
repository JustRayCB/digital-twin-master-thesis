"""Routine Compiler.

Validates and compiles Logic Builder graphs into executable structures.
Ensures DAG properties and trigger-to-action connectivity.
"""

from typing import Any

import networkx as nx

from dt.communication.adapters import load
from dt.communication.dataclasses.controller import (Action, CompiledRule,
                                                     RoutineGraph, Trigger)


class RoutineCompiler:
    """Compiler for Logic Builder routines."""

    def validate(self, graph: RoutineGraph) -> None:
        """Validate the routine graph.

        Checks:
        1. Schema validity (via dataclass loading)
        2. DAG property (no cycles)
        3. Connectivity (triggers connected to actions)

        Raises
        ------
        ValueError
            If the graph is invalid.
        """

        graph_nx = self._build_nx(graph)

        if not nx.is_directed_acyclic_graph(graph_nx):
            raise ValueError("Routine graph contains cycles.")

        self._validate_nodes(graph)

        triggers = [node.id for node in graph.nodes if node.kind == "trigger"]
        actions = [node.id for node in graph.nodes if node.kind == "action"]

        if not triggers:
            raise ValueError("Routine must have at least one trigger.")
        if not actions:
            raise ValueError("Routine must have at least one action.")

        reachable = set()
        for trigger_id in triggers:
            reachable.update(nx.descendants(graph_nx, trigger_id))
            reachable.add(trigger_id)
        for action_id in actions:
            if action_id not in reachable:
                raise ValueError(f"Action {action_id} is not reachable from any trigger.")

    def compile(self, graph: RoutineGraph) -> list[CompiledRule]:
        """Compile the graph into a flat rule format for runtime evaluation."""
        self.validate(graph)

        graph_nx = self._build_nx(graph)

        triggers = [node for node in graph.nodes if node.kind == "trigger"]
        actions = [node for node in graph.nodes if node.kind == "action"]

        rules: list[CompiledRule] = []
        for trigger in sorted(triggers, key=lambda node: node.id):
            trigger_payload = self._compile_trigger(trigger)
            descendants = nx.descendants(graph_nx, trigger.id)
            trigger_actions: list[Action] = []

            for action in sorted(actions, key=lambda node: node.id):
                if action.id in descendants:
                    trigger_actions.append(
                        Action(
                            actuator_id=action.action.actuator_id,
                            command=action.action.command,
                            duration=action.action.duration,
                        )
                    )

            if trigger_actions:
                rules.append(
                    CompiledRule(
                        id=trigger.id,
                        trigger=trigger_payload,
                        actions=trigger_actions,
                    )
                )

        return rules

    def _compile_trigger(self, trigger: Any) -> Trigger:
        if trigger.kind != "trigger" or trigger.trigger is None:
            raise ValueError(f"Trigger {trigger.id} missing trigger config")

        if trigger.trigger.type == "time":
            if not trigger.trigger.time:
                raise ValueError(f"Trigger {trigger.id} missing time")
            return Trigger(type="time", time=trigger.trigger.time)

        if trigger.trigger.type == "date":
            if not trigger.trigger.date:
                raise ValueError(f"Trigger {trigger.id} missing date")
            return Trigger(type="date", date=trigger.trigger.date)

        if trigger.trigger.type == "interval":
            if trigger.trigger.every_days is None:
                raise ValueError(f"Trigger {trigger.id} missing every_days")
            if not trigger.trigger.at:
                raise ValueError(f"Trigger {trigger.id} missing at time")
            return Trigger(
                type="interval",
                every_days=trigger.trigger.every_days,
                at=trigger.trigger.at,
            )

        if trigger.trigger.type == "sensor":
            if not trigger.trigger.topic:
                raise ValueError(f"Trigger {trigger.id} missing topic")
            if trigger.trigger.op is None or trigger.trigger.value is None:
                raise ValueError(f"Trigger {trigger.id} missing operator or value")
            return Trigger(
                type="sensor",
                topic=trigger.trigger.topic,
                op=trigger.trigger.op,
                value=trigger.trigger.value,
            )

        raise ValueError(f"Trigger {trigger.id} has unsupported type {trigger.trigger.type}")

    def _build_nx(self, graph: RoutineGraph) -> nx.DiGraph:
        graph_nx = nx.DiGraph()
        for node in graph.nodes:
            graph_nx.add_node(node.id)
        for edge in graph.edges:
            graph_nx.add_edge(edge.source, edge.target)
        return graph_nx

    def _validate_nodes(self, graph: RoutineGraph) -> None:
        for node in graph.nodes:
            if node.kind not in {"trigger", "action"}:
                raise ValueError(f"Unsupported node kind {node.kind}")
            if node.kind == "trigger" and node.trigger is None:
                raise ValueError(f"Trigger {node.id} missing trigger config")
            if node.kind == "action" and node.action is None:
                raise ValueError(f"Action {node.id} missing action config")
