import math
from typing import Callable, Dict, List, Optional, Tuple

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely.affinity import rotate, translate
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    Point,
    box,
)
from shapely.ops import linemerge, transform, unary_union


STEP = 30.0

SURFACE_PENALTY = {
    "paved": 1.0,
    "asphalt": 1.0,
    "concrete": 1.0,
    "gravel": 1.05,
    "dirt": 1.10,
    "sand": 1.20,
    "unknown": 1.0,
}


# ============================================================
# Elevation + line sampling
# ============================================================

def default_elevation_fn(lat: float, lon: float) -> float:
    """
    Synthetic elevation function used for demo purposes.
    This keeps the public repo self-contained.
    """
    return (
        120.0
        + 25.0 * math.sin(lat * 0.03)
        + 18.0 * math.cos(lon * 0.04)
        + 8.0 * math.sin((lat + lon) * 0.02)
    )


def _get_local_metric_crs_from_line(line_wgs84: LineString) -> CRS:
    centroid = line_wgs84.centroid
    lon, lat = centroid.x, centroid.y
    zone = int((lon + 180) // 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def _project_linestring(line: LineString, src_crs, dst_crs) -> LineString:
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return transform(transformer.transform, line)


def sample_line_every_x_meters(
    line: LineString,
    step: float = STEP,
    line_crs="EPSG:4326",
) -> Tuple[List[Point], List[float], float]:
    if line.is_empty:
        return [], [], 0.0

    src_crs = CRS.from_user_input(line_crs)

    if src_crs.to_epsg() != 4326:
        line_wgs84 = _project_linestring(line, src_crs, "EPSG:4326")
    else:
        line_wgs84 = line

    metric_crs = _get_local_metric_crs_from_line(line_wgs84)
    line_metric = _project_linestring(line_wgs84, "EPSG:4326", metric_crs)

    length_m = float(line_metric.length)
    if length_m == 0:
        return [Point(line_wgs84.coords[0])], [0.0], 0.0

    if length_m <= step:
        distances_m = [0.0, length_m]
    else:
        distances_m = list(np.arange(0, length_m, step)) + [length_m]

    pts_metric = [line_metric.interpolate(d) for d in distances_m]
    transformer_back = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True)
    pts_wgs84 = [transform(transformer_back.transform, pt) for pt in pts_metric]

    return pts_wgs84, distances_m, length_m


def slope_and_curvature_from_line(
    line: LineString,
    elevation_fn: Callable[[float, float], float],
    line_crs="EPSG:4326",
    step: float = STEP,
) -> Tuple[float, float]:
    pts_wgs84, distances_m, _ = sample_line_every_x_meters(
        line=line,
        step=step,
        line_crs=line_crs,
    )

    elevations = [float(elevation_fn(p.y, p.x)) for p in pts_wgs84]

    if len(elevations) < 2:
        return 0.0, 0.0

    ds = np.diff(distances_m)
    dz = np.diff(elevations)

    valid = ds > 0
    if not np.any(valid):
        return 0.0, 0.0

    gradients = dz[valid] / ds[valid]
    mean_slope = float(np.mean(np.abs(gradients)))

    if len(gradients) < 2:
        return mean_slope, 0.0

    ds_grad = ds[1:]
    valid_curv = ds_grad > 0
    if not np.any(valid_curv):
        return mean_slope, 0.0

    curvatures = np.diff(gradients)[valid_curv] / ds_grad[valid_curv]
    mean_curvature = float(np.mean(np.abs(curvatures))) if len(curvatures) else 0.0

    return mean_slope, mean_curvature


# ============================================================
# Penalization model
# ============================================================

def _saturated_term(value: float, ref: float) -> float:
    value = float(value)
    ref = float(ref)

    if ref <= 0:
        return 0.0

    x = value / ref
    return (x ** 2) / (1.0 + x ** 2)


def _saturated_excess_term(value: float, ref: float, base: float = 0.0) -> float:
    value = float(value)
    ref = float(ref)
    base = float(base)

    if ref <= base:
        return 0.0

    excess = max(0.0, value - base)
    scale = ref - base
    x = excess / scale
    return (x ** 2) / (1.0 + x ** 2)


def _edge_impedance_components(
    length: float,
    slope: float,
    curvature: float,
    surface_factor: float = 1.0,
    slope_ref: float = 0.0,
    curvature_ref: float = 0.0,
    curvature_base: float = 0.0,
) -> Dict[str, float]:
    length = float(length)
    slope = float(slope)
    curvature = float(curvature)
    surface_factor = float(surface_factor)

    slope_term = _saturated_term(slope, slope_ref)
    curvature_term = _saturated_excess_term(
        curvature,
        curvature_ref,
        base=curvature_base,
    )

    impedance = surface_factor * (1.0 + slope_term + curvature_term)
    weight = length * impedance

    slope_penalty = length * surface_factor * slope_term
    curvature_penalty = length * surface_factor * curvature_term
    surface_penalty = length * (surface_factor - 1.0)
    penalty_total = weight - length

    return {
        "impedance": float(impedance),
        "weight": float(weight),
        "slope_term": float(slope_term),
        "curvature_term": float(curvature_term),
        "slope_penalty": float(slope_penalty),
        "curvature_penalty": float(curvature_penalty),
        "surface_penalty": float(surface_penalty),
        "penalty_total": float(penalty_total),
    }


def compute_edge_topography(
    graph: nx.MultiGraph,
    elevation_fn: Callable[[float, float], float],
    step: float = STEP,
) -> pd.DataFrame:
    edge_rows = []
    graph_crs = graph.graph.get("crs", "EPSG:4326")

    for u, v, key, data in graph.edges(data=True, keys=True):
        base_length = data.get("length")
        if base_length is None:
            continue

        base_length = float(base_length)
        if base_length <= 0:
            continue

        line = data.get(
            "geometry",
            LineString([
                (graph.nodes[u]["x"], graph.nodes[u]["y"]),
                (graph.nodes[v]["x"], graph.nodes[v]["y"]),
            ]),
        )

        slope, curvature = slope_and_curvature_from_line(
            line=line,
            elevation_fn=elevation_fn,
            line_crs=graph_crs,
            step=step,
        )

        graph[u][v][key]["slope"] = float(slope)
        graph[u][v][key]["curvature"] = float(curvature)
        graph[u][v][key]["flat_length"] = float(base_length)

        edge_rows.append((u, v, key, base_length, slope, curvature))

    return pd.DataFrame(
        edge_rows,
        columns=["u", "v", "key", "length", "slope", "curvature"],
    )


def _adaptive_quantile_from_tail_ratio(
    values,
    q_min: float = 0.75,
    q_max: float = 0.95,
    r_min: float = 1.2,
    r_max: float = 4.0,
) -> Dict[str, float]:
    values = pd.Series(values).dropna()
    values = values[values >= 0]

    if values.empty:
        return {"q": q_min, "q75": 0.0, "q95": 0.0, "tail_ratio": 1.0}

    q75 = float(values.quantile(0.75))
    q95 = float(values.quantile(0.95))

    if q75 <= 0:
        tail_ratio = float("inf") if q95 > 0 else 1.0
    else:
        tail_ratio = q95 / q75

    if tail_ratio <= r_min:
        q = q_min
    elif tail_ratio >= r_max:
        q = q_max
    else:
        t = (tail_ratio - r_min) / (r_max - r_min)
        q = q_min + t * (q_max - q_min)

    return {
        "q": float(q),
        "q75": float(q75),
        "q95": float(q95),
        "tail_ratio": float(tail_ratio),
    }


def _compute_reference_percentiles(edge_topography_df: pd.DataFrame) -> Dict[str, float]:
    if edge_topography_df.empty:
        return {
            "slope_ref": 0.0,
            "curvature_ref": 0.0,
            "curvature_base": 0.0,
            "slope_q": 0.75,
            "curvature_q": 0.75,
            "slope_tail_ratio": 1.0,
            "curvature_tail_ratio": 1.0,
        }

    slope_info = _adaptive_quantile_from_tail_ratio(edge_topography_df["slope"])
    curvature_info = _adaptive_quantile_from_tail_ratio(edge_topography_df["curvature"])

    slope_ref = float(edge_topography_df["slope"].quantile(slope_info["q"]))
    curvature_ref = float(edge_topography_df["curvature"].quantile(curvature_info["q"]))
    curvature_base = float(edge_topography_df["curvature"].quantile(0.75))

    return {
        "slope_ref": slope_ref,
        "curvature_ref": curvature_ref,
        "curvature_base": curvature_base,
        "slope_q": float(slope_info["q"]),
        "curvature_q": float(curvature_info["q"]),
        "slope_tail_ratio": float(slope_info["tail_ratio"]),
        "curvature_tail_ratio": float(curvature_info["tail_ratio"]),
    }


def calculate_edge_penalties(
    graph: nx.MultiGraph,
    elevation_fn: Callable[[float, float], float] = default_elevation_fn,
    step: float = STEP,
) -> pd.DataFrame:
    edge_topography_df = compute_edge_topography(
        graph=graph,
        elevation_fn=elevation_fn,
        step=step,
    )

    refs = _compute_reference_percentiles(edge_topography_df)

    slope_ref = refs["slope_ref"]
    curvature_ref = refs["curvature_ref"]
    curvature_base = refs["curvature_base"]

    edge_rows = []

    for row in edge_topography_df.itertuples(index=False):
        u = row.u
        v = row.v
        key = row.key
        base_length = float(row.length)
        slope = float(row.slope)
        curvature = float(row.curvature)

        data = graph[u][v][key]
        surface_type = str(data.get("surface", "unknown")).lower()
        surface_factor = SURFACE_PENALTY.get(surface_type, 1.2)

        components = _edge_impedance_components(
            length=base_length,
            slope=slope,
            curvature=curvature,
            surface_factor=surface_factor,
            slope_ref=slope_ref,
            curvature_ref=curvature_ref,
            curvature_base=curvature_base,
        )

        edge_rows.append((
            u, v, key, base_length, slope, curvature,
            float(surface_factor),
            float(slope_ref),
            float(curvature_ref),
            float(curvature_base),
            float(components["slope_term"]),
            float(components["curvature_term"]),
            float(components["impedance"]),
            float(components["slope_penalty"]),
            float(components["curvature_penalty"]),
            float(components["surface_penalty"]),
            float(components["penalty_total"]),
            float(components["weight"]),
        ))

    edges_df = pd.DataFrame(
        edge_rows,
        columns=[
            "u",
            "v",
            "key",
            "length",
            "slope",
            "curvature",
            "surface_factor",
            "slope_ref",
            "curvature_ref",
            "curvature_base",
            "slope_term",
            "curvature_term",
            "impedance",
            "slope_penalty",
            "curvature_penalty",
            "surface_penalty",
            "penalty_total",
            "penalized_length",
        ],
    )

    edges_df["flat_length"] = edges_df["length"]

    for row in edges_df.itertuples(index=False):
        edge = graph[row.u][row.v][row.key]
        edge["length"] = float(row.length)
        edge["flat_length"] = float(row.flat_length)
        edge["slope"] = float(row.slope)
        edge["curvature"] = float(row.curvature)
        edge["surface_factor"] = float(row.surface_factor)
        edge["slope_ref"] = float(row.slope_ref)
        edge["curvature_ref"] = float(row.curvature_ref)
        edge["curvature_base"] = float(row.curvature_base)
        edge["slope_term"] = float(row.slope_term)
        edge["curvature_term"] = float(row.curvature_term)
        edge["impedance"] = float(row.impedance)
        edge["slope_penalty"] = float(row.slope_penalty)
        edge["curvature_penalty"] = float(row.curvature_penalty)
        edge["surface_penalty"] = float(row.surface_penalty)
        edge["penalty_total"] = float(row.penalty_total)
        edge["penalized_length"] = float(row.penalized_length)

    graph.graph["slope_ref"] = float(slope_ref)
    graph.graph["curvature_ref"] = float(curvature_ref)
    graph.graph["curvature_base"] = float(curvature_base)
    graph.graph["slope_reference_quantile"] = float(refs["slope_q"])
    graph.graph["curvature_reference_quantile"] = float(refs["curvature_q"])
    graph.graph["slope_tail_ratio"] = float(refs["slope_tail_ratio"])
    graph.graph["curvature_tail_ratio"] = float(refs["curvature_tail_ratio"])

    return edges_df


# ============================================================
# Local access grid
# ============================================================

def _point_key(point: Point, snap: float = 1e-6) -> Tuple[float, float]:
    return (round(point.x / snap) * snap, round(point.y / snap) * snap)


def _extract_points_from_intersection(geom) -> List[Point]:
    if geom.is_empty:
        return []

    if isinstance(geom, Point):
        return [geom]

    if isinstance(geom, MultiPoint):
        return list(geom.geoms)

    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if not coords:
            return []
        return [Point(coords[0]), Point(coords[-1])]

    if isinstance(geom, MultiLineString):
        pts = []
        for line in geom.geoms:
            coords = list(line.coords)
            if coords:
                pts.append(Point(coords[0]))
                pts.append(Point(coords[-1]))
        return pts

    if isinstance(geom, GeometryCollection):
        pts = []
        for g in geom.geoms:
            pts.extend(_extract_points_from_intersection(g))
        return pts

    return []


def _deduplicate_points(points: List[Point], tolerance: float = 1e-6) -> List[Point]:
    unique = []
    for p in points:
        if not any(p.distance(q) <= tolerance for q in unique):
            unique.append(p)
    return unique


def _project_point_onto_line(point: Point, line: LineString) -> Point:
    return line.interpolate(line.project(point))


def _segments_from_linestring(curve: LineString) -> List[LineString]:
    return [LineString([curve.coords[i], curve.coords[i + 1]]) for i in range(len(curve.coords) - 1)]


def _build_access_geometry_from_local_path(local_graph: nx.Graph, best_path: List[str]) -> Dict[str, object]:
    if not best_path:
        return {"connection_line_geom": None, "connection_length": None}

    if len(best_path) == 1:
        pt = local_graph.nodes[best_path[0]]["geometry"]
        return {"connection_line_geom": pt, "connection_length": 0.0}

    segments = []
    total_length = 0.0

    for u, v in zip(best_path[:-1], best_path[1:]):
        edge_data = local_graph.get_edge_data(u, v)
        geom = edge_data["geometry"]
        segments.append(geom)
        total_length += edge_data.get("length", geom.length)

    try:
        merged = linemerge(segments)
    except Exception:
        merged = segments[0] if len(segments) == 1 else unary_union(segments)

    return {
        "connection_line_geom": merged,
        "connection_length": total_length,
    }


def _get_reference_point_on_road(point_geom: Point, nearest_line_row: pd.Series) -> Dict[str, object]:
    if len(nearest_line_row.geometry.coords) > 2:
        segs = _segments_from_linestring(nearest_line_row.geometry)
        distances = [seg.distance(point_geom) for seg in segs]
        reference_segment = segs[int(pd.Series(distances).idxmin())]
    else:
        reference_segment = nearest_line_row.geometry

    reference_point = _project_point_onto_line(point_geom, reference_segment)
    distance_to_road = point_geom.distance(reference_point)

    return {
        "reference_point": reference_point,
        "reference_segment": reference_segment,
        "distance_to_road": distance_to_road,
    }


def _build_oriented_grid_geometry(
    point_geom: Point,
    reference_point: Point,
    distance_to_road: float,
) -> Dict[str, object]:
    grid_size = max(2 * distance_to_road, 1.0)
    step = grid_size / 3.0

    local_lines = []

    for i in range(7):
        x = -grid_size / 2.0 + i * step
        local_lines.append(LineString([(x, 0.0), (x, grid_size)]))

    for j in range(7):
        y = j * step
        local_lines.append(LineString([(-grid_size / 2.0, y), (grid_size / 2.0, y)]))

    dx = reference_point.x - point_geom.x
    dy = reference_point.y - point_geom.y

    angle_rad = -math.atan2(dx, dy)
    angle_deg = math.degrees(angle_rad)

    rotated_lines = [rotate(line, angle_deg, origin=(0.0, 0.0)) for line in local_lines]
    world_lines = [translate(line, xoff=point_geom.x, yoff=point_geom.y) for line in rotated_lines]

    grid_union = unary_union(world_lines)
    grid_bbox = box(*grid_union.bounds)

    return {
        "grid_lines": world_lines,
        "grid_size": grid_size,
        "step": step,
        "angle_rad": angle_rad,
        "angle_deg": angle_deg,
        "grid_bbox": grid_bbox,
    }


def _get_road_intersections_with_grid(
    grid_lines: List[LineString],
    lines_df: gpd.GeoDataFrame,
    new_lines_df: Optional[gpd.GeoDataFrame] = None,
    tolerance: float = 1e-6,
) -> List[Dict[str, object]]:
    frames = [lines_df]
    if new_lines_df is not None and not new_lines_df.empty:
        frames.append(new_lines_df)

    roads_df = pd.concat(frames, ignore_index=False)
    roads_df = gpd.GeoDataFrame(roads_df, geometry="geometry", crs=lines_df.crs)

    grid_union = unary_union(grid_lines)
    grid_bbox = box(*grid_union.bounds)

    candidate_roads = roads_df.loc[roads_df.geometry.intersects(grid_bbox)]

    intersections = []
    used_points = []

    for road_idx, road_row in candidate_roads.iterrows():
        for grid_line_idx, grid_line in enumerate(grid_lines):
            inter_geom = grid_line.intersection(road_row.geometry)
            points = _extract_points_from_intersection(inter_geom)

            for pt in points:
                if any(pt.distance(q) <= tolerance for q in used_points):
                    continue
                intersections.append({
                    "intersection_point": pt,
                    "road_line": road_row,
                    "road_line_id": road_idx,
                    "grid_line_index": grid_line_idx,
                })
                used_points.append(pt)

    return intersections


def _local_grid_edge_weight_from_line(
    line: LineString,
    elevation_fn: Callable[[float, float], float],
    base_length: Optional[float] = None,
    line_crs="EPSG:4326",
    slope_ref: float = 0.0,
    curvature_ref: float = 0.0,
    curvature_base: float = 0.0,
) -> Tuple[float, float, float, float, float, float]:
    if line.is_empty:
        return 0.0, 1.0, 0.0, 0.0, 0.0, 0.0

    flat_length = float(base_length if base_length is not None else line.length)
    if flat_length == 0:
        return 0.0, 1.0, 0.0, 0.0, 0.0, 0.0

    slope, curvature = slope_and_curvature_from_line(
        line=line,
        elevation_fn=elevation_fn,
        line_crs=line_crs,
        step=STEP,
    )

    components = _edge_impedance_components(
        length=flat_length,
        slope=slope,
        curvature=curvature,
        surface_factor=1.0,
        slope_ref=slope_ref,
        curvature_ref=curvature_ref,
        curvature_base=curvature_base,
    )

    return (
        components["weight"],
        components["impedance"],
        float(slope),
        float(curvature),
        components["slope_penalty"],
        components["curvature_penalty"],
    )


def _build_local_grid_graph(
    point_geom: Point,
    grid_lines: List[LineString],
    road_intersections: List[Dict[str, object]],
    elevation_fn: Callable[[float, float], float],
    line_crs="EPSG:4326",
    slope_ref: float = 0.0,
    curvature_ref: float = 0.0,
    curvature_base: float = 0.0,
    tolerance: float = 1e-6,
) -> Dict[str, object]:
    local_graph = nx.Graph()

    all_points = [point_geom]

    for i in range(len(grid_lines)):
        for j in range(i + 1, len(grid_lines)):
            inter = grid_lines[i].intersection(grid_lines[j])
            all_points.extend(_extract_points_from_intersection(inter))

    road_intersection_points = [item["intersection_point"] for item in road_intersections]
    all_points.extend(road_intersection_points)
    all_points = _deduplicate_points(all_points, tolerance=tolerance)

    node_points = {}
    target_node_to_intersection = {}

    def get_or_create_node_id(point: Point) -> str:
        key = _point_key(point, snap=tolerance)
        snapped_point = Point(key[0], key[1])

        if key not in node_points:
            node_id = f"grid_{len(node_points)}"
            node_points[key] = {"node_id": node_id, "geometry": snapped_point}
            local_graph.add_node(
                node_id,
                x=snapped_point.x,
                y=snapped_point.y,
                geometry=snapped_point,
            )

        return node_points[key]["node_id"]

    for pt in all_points:
        get_or_create_node_id(pt)

    for line_idx, grid_line in enumerate(grid_lines):
        line_nodes = []

        for pt in all_points:
            if pt.distance(grid_line) <= tolerance:
                projected = grid_line.interpolate(grid_line.project(pt))
                node_id = get_or_create_node_id(projected)
                pos = grid_line.project(projected)
                line_nodes.append({"node_id": node_id, "position": pos})

        if not line_nodes:
            continue

        line_nodes.sort(key=lambda x: x["position"])

        ordered_unique = []
        seen_ids = set()
        for item in line_nodes:
            if item["node_id"] not in seen_ids:
                ordered_unique.append(item)
                seen_ids.add(item["node_id"])

        for offset in [1, 2]:
            for seg_idx, i in enumerate(range(len(ordered_unique) - offset)):
                a = ordered_unique[i]
                b = ordered_unique[i + offset]

                u = a["node_id"]
                v = b["node_id"]

                if u == v:
                    continue

                p1 = local_graph.nodes[u]["geometry"]
                p2 = local_graph.nodes[v]["geometry"]

                geom = LineString([p1, p2])
                length = geom.length
                if length <= tolerance:
                    continue

                weight, impedance, slope, curvature, slope_penalty, curvature_penalty = _local_grid_edge_weight_from_line(
                    line=geom,
                    elevation_fn=elevation_fn,
                    base_length=length,
                    line_crs=line_crs,
                    slope_ref=slope_ref,
                    curvature_ref=curvature_ref,
                    curvature_base=curvature_base,
                )

                if not local_graph.has_edge(u, v):
                    local_graph.add_edge(
                        u,
                        v,
                        geometry=geom,
                        length=length,
                        weight=weight,
                        impedance=impedance,
                        slope=slope,
                        curvature=curvature,
                        slope_penalty=slope_penalty,
                        curvature_penalty=curvature_penalty,
                        grid_line_index=line_idx,
                        segment_index=f"{offset}_{seg_idx}",
                        edge_type="grid",
                    )

    poi_node = get_or_create_node_id(point_geom)

    target_nodes = []
    for item in road_intersections:
        pt = item["intersection_point"]
        target_node = get_or_create_node_id(pt)
        target_nodes.append(target_node)
        target_node_to_intersection[target_node] = item

    target_nodes = list(dict.fromkeys(target_nodes))

    return {
        "local_graph": local_graph,
        "poi_node": poi_node,
        "target_nodes": target_nodes,
        "target_node_to_intersection": target_node_to_intersection,
    }


def _find_best_road_intersection_via_local_graph(
    local_graph: nx.Graph,
    poi_node: str,
    target_nodes: List[str],
    weight: str = "weight",
) -> Dict[str, object]:
    best_target_node = None
    best_path = None
    best_cost = float("inf")

    for target_node in target_nodes:
        if target_node == poi_node:
            return {
                "best_target_node": target_node,
                "best_path": [poi_node],
                "best_cost": 0.0,
            }

        try:
            path = nx.shortest_path(local_graph, source=poi_node, target=target_node, weight=weight)
            cost = nx.shortest_path_length(local_graph, source=poi_node, target=target_node, weight=weight)
        except nx.NetworkXNoPath:
            continue

        if cost < best_cost:
            best_target_node = target_node
            best_path = path
            best_cost = cost

    return {
        "best_target_node": best_target_node,
        "best_path": best_path,
        "best_cost": best_cost,
    }


def compute_best_local_access_path(
    point_geom: Point,
    nearest_line: pd.Series,
    lines_df: gpd.GeoDataFrame,
    new_lines_df: Optional[gpd.GeoDataFrame] = None,
    elevation_fn: Callable[[float, float], float] = default_elevation_fn,
    line_crs="EPSG:4326",
    slope_ref: float = 0.0,
    curvature_ref: float = 0.0,
    curvature_base: float = 0.0,
    tolerance: float = 1e-6,
) -> Dict[str, object]:
    reference = _get_reference_point_on_road(point_geom, nearest_line)

    if reference["distance_to_road"] == 0:
        return {
            "connection_point": reference["reference_point"],
            "target_line": nearest_line,
            "connection_line_geom": reference["reference_point"],
            "connection_length": 0.0,
            "best_path": None,
            "best_cost": 0.0,
            "road_intersections": [],
            "grid_lines": [],
        }

    grid = _build_oriented_grid_geometry(
        point_geom=point_geom,
        reference_point=reference["reference_point"],
        distance_to_road=reference["distance_to_road"],
    )

    road_intersections = _get_road_intersections_with_grid(
        grid_lines=grid["grid_lines"],
        lines_df=lines_df,
        new_lines_df=new_lines_df,
        tolerance=tolerance,
    )

    local_graph_data = _build_local_grid_graph(
        point_geom=point_geom,
        grid_lines=grid["grid_lines"],
        road_intersections=road_intersections,
        elevation_fn=elevation_fn,
        line_crs=line_crs,
        slope_ref=slope_ref,
        curvature_ref=curvature_ref,
        curvature_base=curvature_base,
        tolerance=tolerance,
    )

    local_graph = local_graph_data["local_graph"]
    poi_node = local_graph_data["poi_node"]
    target_nodes = local_graph_data["target_nodes"]

    if not target_nodes:
        raise ValueError("No reachable road intersections were generated by the local grid.")

    best = _find_best_road_intersection_via_local_graph(
        local_graph=local_graph,
        poi_node=poi_node,
        target_nodes=target_nodes,
        weight="weight",
    )

    if best["best_target_node"] is None:
        raise ValueError("Target intersections exist, but none is reachable from the POI.")

    target_intersection = local_graph_data["target_node_to_intersection"][best["best_target_node"]]
    access_geom = _build_access_geometry_from_local_path(
        local_graph=local_graph,
        best_path=best["best_path"],
    )

    return {
        "connection_point": target_intersection["intersection_point"],
        "target_line": target_intersection["road_line"],
        "connection_line_geom": access_geom["connection_line_geom"],
        "connection_length": access_geom["connection_length"],
        "best_path": best["best_path"],
        "best_cost": best["best_cost"],
        "road_intersections": road_intersections,
        "grid_lines": grid["grid_lines"],
    }