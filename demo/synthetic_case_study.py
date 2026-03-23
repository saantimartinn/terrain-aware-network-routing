import networkx as nx
from simplified_penalty_model import compute_cost

def build_graph():
    G = nx.Graph()

    G.add_edge("A", "B", length=100, terrain="urban", elev=2)
    G.add_edge("B", "C", length=100, terrain="forest", elev=10)
    G.add_edge("A", "C", length=150, terrain="urban", elev=1)

    return G

def apply_costs(G):
    for u, v, data in G.edges(data=True):
        data["weight"] = compute_cost(
            data["length"],
            data["terrain"],
            data["elev"]
        )

def run():
    G = build_graph()
    apply_costs(G)

    path = nx.shortest_path(G, "A", "C", weight="weight")
    print("Best path:", path)

if __name__ == "__main__":
    run()