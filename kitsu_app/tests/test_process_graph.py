from kitsu_app.models.process_graph import ProcessGraph

def test_graph_creation():
    graph = ProcessGraph()
    graph.add_node("Process A")
    graph.add_node("Machine B")
    graph.add_node("Operator C")

    assert len(graph.nodes) == 3



if __name__ == "__main__":
    test_graph_creation()
