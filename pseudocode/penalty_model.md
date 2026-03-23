# Penalty Model

FOR each edge:
    length = compute_length(edge)
    terrain = lookup_terrain(edge)
    slope = compute_slope(edge)

    terrain_factor = map_terrain_to_penalty(terrain)
    slope_factor = 1 + slope

    cost = length * terrain_factor * slope_factor