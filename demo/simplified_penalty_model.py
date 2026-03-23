import numpy as np

def terrain_factor(terrain):
    mapping = {
        "urban": 1.0,
        "forest": 1.5,
        "water": 3.0
    }
    return mapping.get(terrain, 1.0)

def slope_factor(elevation_diff, distance):
    if distance == 0:
        return 1.0
    slope = elevation_diff / distance
    return 1 + abs(slope)

def compute_cost(length, terrain, elevation_diff):
    return length * terrain_factor(terrain) * slope_factor(elevation_diff, length)


if __name__ == "__main__":
    cost = compute_cost(100, "forest", 10)
    print("Cost:", cost)