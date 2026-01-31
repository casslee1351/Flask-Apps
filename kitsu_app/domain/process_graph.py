from dataclasses import dataclass
from typing import Dict, Set, List


@dataclass(frozen=True)
class ProcessNode:
    """
    A single process step in the manufacturing flow.
    """
    id: str
    name: str


class ProcessGraph:
    """
    Directed graph describing valid process transitions.
    """

    def __init__(self):
        self.nodes: Dict[str, ProcessNode] = {}
        self.edges: Dict[str, Set[str]] = {}

    # ----------------------------
    # Node management
    # ----------------------------

    def add_node(self, node_id: str, name: str):
        if node_id in self.nodes:
            raise ValueError(f"Node '{node_id}' already exists")

        self.nodes[node_id] = ProcessNode(node_id, name)
        self.edges[node_id] = set()

    # ----------------------------
    # Edge management
    # ----------------------------

    def add_edge(self, from_node: str, to_node: str):
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError("Both nodes must exist before adding an edge")

        self.edges[from_node].add(to_node)

    # ----------------------------
    # Queries
    # ----------------------------

    def allowed_next_steps(self, node_id: str) -> Set[str]:
        return self.edges.get(node_id, set())

    def is_valid_transition(self, from_node: str, to_node: str) -> bool:
        return to_node in self.edges.get(from_node, set())

    def is_valid_path(self, path: List[str]) -> bool:
        """
        Check whether an observed process sequence is valid.
        """
        for i in range(len(path) - 1):
            if not self.is_valid_transition(path[i], path[i + 1]):
                return False
        return True
