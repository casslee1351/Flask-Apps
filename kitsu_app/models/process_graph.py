from dataclasses import dataclass

ALLOWED_PROCESSES = ["Process A", "Process B", "Process C"]
ALLOWED_MACHINES = ["Machine A", "Machine B", "Machine C"]
ALLOWED_OPERATORS = ["Operator A", "Operator B", "Operator C"]

ALLOWED_EDGES = {
    "process": {"machine"},
    "machine": {"operator"},
}
### redesign graph object to accurately reflect the time cycle process

# class ProcessNode:
#     def __init__(self, name: str, node_type: str):
#         self.name = name
#         self.node_type = node_type  # "process" | "machine" | "operator"

#     def __repr__(self):
#         return f"<{self.node_type.upper()}: {self.name}>"


#     def add_next(self, node):
#         if not isinstance(node, ProcessNode):
#             raise TypeError("Next node must be a ProcessNode")
#         self.next_nodes.append(node)

@dataclass(frozen=True)
class ProcessNode:
    process: str
    machine: str
    operator: str
    time_type: str  # e.g. "machine", "operator", "process"

    @property
    def id(self):
        return (self.process, self.machine, self.operator, self.time_type)

    def group_key(self, level: str):
        """
        Projection key for grouping
        """
        if level == "process":
            return self.process
        if level == "machine":
            return self.machine
        if level == "operator":
            return self.operator
        if level == "time_type":
            return self.time_type
        raise ValueError(f"Unknown grouping level: {level}")
    
class ProcessGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}  # (from_id, to_id) -> count

    def add_node(self, node: ProcessNode):
        self.nodes[node.id] = node

    def add_edge(self, from_node, to_node):
        key = (from_node.id, to_node.id)
        self.edges[key] = self.edges.get(key, 0) + 1


# class ProcessGraph:
#     def __init__(self):
#         self.nodes = []
#         self.edges = []

#     def infer_type(self, name: str) -> str:
#         name = name.lower()
#         if name.startswith("process"):
#             return "process"
#         if name.startswith("machine"):
#             return "machine"
#         if name.startswith("operator"):
#             return "operator"
#         raise ValueError(f"Invalid node name: {name}")

#     def find_node(self, name: str, node_type: str):
#         for n in self.nodes:
#             if n.name == name and n.node_type == node_type:
#                 return n
#         return None

#     def add_node(self, name: str):
#         node_type = self.infer_type(name)

#         if self.find_node(name, node_type) is None:
#             node = ProcessNode(name, node_type)
#             self.nodes.append(node)

#         return self.find_node(name, node_type)
    

#     def add_edge(self, from_name: str, to_name: str):
#         from_node = self.add_node(from_name)
#         to_node = self.add_node(to_name)

#         if to_node.node_type not in ALLOWED_EDGES.get(from_node.node_type, set()):
#             raise ValueError(
#                 f"Invalid edge: {from_node.node_type} → {to_node.node_type}"
#             )

#         self.edges.append((from_node, to_node))

