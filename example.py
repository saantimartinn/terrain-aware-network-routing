import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point

from terrain_routing import (
    calculate_edge_penalties,
    compute_best_local_access_path,
    default_elevation_fn,
)


def build_demo_graph():
    G = nx.MultiGraph()
    G.graph["crs"] = "EPSG:4326"

    G.add_node("A", x=0.0, y=0.0)
    G.add_node("B", x=0.0, y=0.01)
    G.add_node("C", x=0.01, y=0.01)
    G.add_node("D", x=0.01, y=0.0)

    edges = [
        ("A", "B", 0, LineString([(0.0, 0.0), (0.0, 0.01)]), 1110, "asphalt"),
        ("B", "C", 0, LineString([(0.0, 0.01), (0.01, 0.01)]), 1110, "gravel"),
        ("C", "D", 0, LineString([(0.01, 0.01), (0.01, 0.0)]), 1110, "dirt"),
        ("D", "A", 0, LineString([(0.01, 0.0), (0.0, 0.0)]), 1110, "asphalt"),
    ]

    for u, v, key, geom, length, surface in edges:
        G.add_edge(
            u,
            v,
            key=key,
            geometry=geom,
            length=length,
            surface=surface,
        )

    return G


def build_demo_lines():
    roads = gpd.GeoDataFrame(
        {
            "road_id": [1, 2],
            "geometry": [
                LineString([(0.0, 0.0), (0.0, 0.01)]),
                LineString([(0.0, 0.01), (0.01, 0.01)]),
            ],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )
    return roads


def main():
    print("\n--- DEMO: EDGE PENALIZATION ---")
    G = build_demo_graph()
    edges_df = calculate_edge_penalties(G, elevation_fn=default_elevation_fn)
    print(edges_df[[
        "u",
        "v",
        "length",
        "slope",
        "curvature",
        "impedance",
        "penalized_length",
    ]])

    print("\n--- DEMO: LOCAL ACCESS GRID ---")
    roads = build_demo_lines()
    poi = Point(0.004, 0.006)
    nearest_line = roads.iloc[0]

    result = compute_best_local_access_path(
        point_geom=poi,
        nearest_line=nearest_line,
        lines_df=roads,
        elevation_fn=default_elevation_fn,
        line_crs="EPSG:4326",
    )

    print("Connection length:", result["connection_length"])
    print("Best path:", result["best_path"])
    print("Connection point:", result["connection_point"])


if __name__ == "__main__":
    main()