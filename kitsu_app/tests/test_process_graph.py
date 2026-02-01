from kitsu_app.models.process_graph import ProcessGraph, ProcessNode

def test_node_identity():
    node1 = ProcessNode(
        process="Process A",
        machine="Machine A",
        operator="Operator A",
        time_type="machine"
    )

    node2 = ProcessNode(
        process="Process A",
        machine="Machine A",
        operator="Operator A",
        time_type="machine"
    )

    assert node1 == node2
    assert node1.id == node2.id

def test_graph_add_node():
    graph = ProcessGraph()

    node = ProcessNode(
        process="Process A",
        machine="Machine B",
        operator="Operator C",
        time_type="machine"
    )

    graph.add_node(node)
    graph.add_node(node)  # add twice

    assert len(graph.nodes) == 1  # no duplicates

def test_graph_add_edge_and_count():
    graph = ProcessGraph()

    n1 = ProcessNode("Process A", "Machine A", "Operator A", "machine")
    n2 = ProcessNode("Process B", "Machine B", "Operator B", "machine")

    graph.add_node(n1)
    graph.add_node(n2)

    graph.add_edge(n1, n2)
    graph.add_edge(n1, n2)

    assert graph.edges[(n1.id, n2.id)] == 2

def test_process_level_projection():
    graph = ProcessGraph()

    n1 = ProcessNode("Process A", "Machine A", "Operator A", "machine")
    n2 = ProcessNode("Process A", "Machine B", "Operator B", "machine")
    n3 = ProcessNode("Process B", "Machine C", "Operator C", "machine")

    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)

    graph.add_edge(n1, n2)
    graph.add_edge(n2, n3)

    process_edges = {}

    for (src, dst), count in graph.edges.items():
        src_p = graph.nodes[src].process
        dst_p = graph.nodes[dst].process
        process_edges[(src_p, dst_p)] = process_edges.get((src_p, dst_p), 0) + count

    assert process_edges[("Process A", "Process A")] == 1
    assert process_edges[("Process A", "Process B")] == 1