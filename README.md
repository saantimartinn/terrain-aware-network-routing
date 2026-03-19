# Terrain-Aware Network Routing
Designed and implemented as part of a real-world network optimization system.

A compact public showcase of two routing components I designed for fiber-network planning:

- **adaptive graph penalization** based on slope and curvature
- **local access grid generation** to connect off-network points to the nearest road corridor

## What this project shows

This repository presents a standalone, simplified implementation of the core algorithmic ideas behind my work on terrain-aware routing.

### 1. Graph penalization
Each edge receives a traversal cost derived from:

- physical length
- slope
- vertical curvature
- surface factor

The final edge weight follows a multiplicative impedance model:

`weight = length * surface_factor * (1 + slope_term + curvature_term)`

Reference values for slope and curvature are selected **adaptively** using upper-tail statistics.

### 2. Local access grid
For points that are not directly on the network, the code builds an oriented local grid between the point and the nearest road segment, evaluates candidate micro-paths, and selects the least-cost access path.

## Files

- `terrain_routing.py` → main implementation
- `example.py` → small runnable demo
- `requirements.txt` → dependencies

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python example.py
```

## Technical highlights

- adaptive quantile selection from tail ratios
- bounded penalty saturation functions
- slope / curvature extraction from sampled elevation profiles
- local grid graph construction
- shortest-path optimization on dynamically generated local graphs

## Note

This public repository is a clean standalone showcase of the algorithmic concepts, designed for portfolio purposes. It does not include the surrounding private project infrastructure or proprietary datasets.