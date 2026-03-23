import networkx as nx

def connect_point_to_graph(graph, point):
    # simplified nearest node
    nearest = list(graph.nodes)[0]

    graph.add_node(point)
    graph.add_edge(point, nearest, weight=1)

    return graph


if __name__ == "__main__":
    G = nx.Graph()
    G.add_edge("A", "B", weight=1)

    G = connect_point_to_graph(G, "POI")

    print(G.edges(data=True))