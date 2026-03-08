from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

# TODO:Add StrEnum for better type safety on node kinds and trigger types, owners, commands


@dataclass
class RoutineNode:
    """Node definition from the Logic Builder graph.

    Attributes
    ----------
    id : str
        Unique node identifier within a graph.
    kind : str
        Node category (trigger, action).
    trigger : Optional[Trigger]
        Trigger configuration when ``kind`` is ``trigger``.
    action : Optional[Action]
        Action configuration when ``kind`` is ``action``.
    """

    id: str
    kind: Literal["trigger", "action"]
    trigger: Optional["Trigger"] = None
    action: Optional["Action"] = None


@dataclass
class RoutineEdge:
    """Directed edge linking two nodes in a routine graph.

    Attributes
    ----------
    source : str
        Source node identifier.
    target : str
        Target node identifier.
    """

    source: str
    target: str


@dataclass
class UiNode:
    """UI-only placement metadata for a graph node."""

    x: float
    y: float
    label: str


@dataclass
class RoutineGraph:
    """Serializable routine graph used by the Logic Builder.

    Attributes
    ----------
    nodes : List[RoutineNode]
        Graph nodes.
    edges : List[RoutineEdge]
        Directed graph edges.
    name : str
        Routine name for editor reconstruction.
    plant_id : int
        Plant identifier for editor reconstruction.
    ui : Optional[Dict[str, UiNode]]
        Optional UI node layout keyed by node id.
    """

    nodes: List[RoutineNode]
    edges: List[RoutineEdge]
    name: str
    plant_id: int
    ui: Optional[Dict[str, UiNode]] = None


TriggerType = Literal["sensor", "time", "date", "interval"]
Operator = Literal["=", "!=", ">", "<", ">=", "<="]


@dataclass
class Trigger:
    """Trigger predicate that activates rule evaluation."""

    type: TriggerType
    topic: Optional[str] = None
    op: Optional[Operator] = None
    value: Optional[float] = None
    time: Optional[str] = None
    date: Optional[str] = None
    every_days: Optional[int] = None
    at: Optional[str] = None


@dataclass
class Action:
    """Action payload for an actuator."""

    actuator_id: int
    command: str
    duration: float


@dataclass
class CompiledRule:
    """Compiled rule ready for runtime evaluation.

    Attributes
    ----------
    id : str
        Stable rule identifier within a compiled routine.
    trigger : Trigger
        Trigger condition that starts rule evaluation.
    actions : List[Action]
        Actions dispatched when trigger matches.
    """

    id: str
    trigger: Trigger
    actions: List[Action] = field(default_factory=list)


@dataclass
class Routine:
    """Persisted routine model.

    Attributes
    ----------
    id : int
        Routine identifier.
    plant_id : int
        Plant identifier owning the routine.
    name : str
        Routine display name.
    enabled : bool
        Whether the routine is active for execution.
    graph : RoutineGraph
        Authoring graph used by the web application.
    compiled_rules : Optional[List[CompiledRule]]
        Compiled execution rules derived from ``graph``.
    created_at : Optional[str]
        Creation timestamp string from persistence layer.
    updated_at : Optional[str]
        Last update timestamp string from persistence layer.
    """

    id: int
    plant_id: int
    name: str
    enabled: bool
    graph: RoutineGraph
    compiled_rules: Optional[List[CompiledRule]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class RoutineUpdate:
    """Patch payload used to update a routine.

    Attributes
    ----------
    plant_id : Optional[int]
        Optional plant identifier update (required for create).
    name : Optional[str]
        Optional routine name update (required for create).
    enabled : Optional[bool]
        Optional enabled flag update.
    graph : Optional[RoutineGraph]
        Optional authoring graph update (required for create).
    compiled_rules : Optional[List[CompiledRule]]
        Optional compiled representation override.
    """

    plant_id: Optional[int] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None
    graph: Optional[RoutineGraph] = None
    compiled_rules: Optional[List[CompiledRule]] = None


@dataclass
class ControlMode:
    """Controller ownership mode for a plant.

    Attributes
    ----------
    plant_id : int
        Plant identifier.
    ai_autopilot_enabled : bool
        Whether AI auto-pilot mode is enabled.
    owner : str
        Current owner of actuator control (`routine` or `ai`).
    updated_at : Optional[str]
        Last mode update timestamp string.
    """

    plant_id: int
    ai_autopilot_enabled: bool
    owner: str  # 'routine' | 'ai'
    updated_at: Optional[str] = None
