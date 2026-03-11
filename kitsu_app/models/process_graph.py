# from dataclasses import dataclass

# ALLOWED_PROCESSES = ["Process A", "Process B", "Process C"]
# ALLOWED_MACHINES = ["Machine A", "Machine B", "Machine C"]
# ALLOWED_OPERATORS = ["Operator A", "Operator B", "Operator C"]

# # ALLOWED_EDGES = {
# #     "process": {"machine"},
# #     "machine": {"operator"},
# # }
# ### redesign graph object to accurately reflect the time cycle process

# @dataclass(frozen=True)
# class ProcessNode:
#     process: str
#     machine: str
#     operator: str
#     time_type: str 

#     @property
#     def id(self):
#         return (self.process, self.machine, self.operator, self.time_type)

#     def group_key(self, level: str):
#         """
#         Projection key for grouping
#         """
#         if level == "process":
#             return self.process
#         if level == "machine":
#             return self.machine
#         if level == "operator":
#             return self.operator
#         if level == "time_type":
#             return self.time_type
#         raise ValueError(f"Unknown grouping level: {level}")
    
# class ProcessGraph:
#     def __init__(self):
#         self.nodes = {}
#         self.edges = {} 

#     def add_node(self, node: ProcessNode):
#         self.nodes[node.id] = node

#     def add_edge(self, from_node, to_node):
#         key = (from_node.id, to_node.id)
#         self.edges[key] = self.edges.get(key, 0) + 1


