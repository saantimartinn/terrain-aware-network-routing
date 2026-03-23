# Terrain-Aware Fiber Routing

> A geospatial routing framework that integrates terrain, elevation, and environmental constraints into network path optimization.

---

##  Overview

This project presents a **terrain-aware routing methodology** for connecting points of interest (POIs) to an existing network while accounting for real-world geographic constraints.

Unlike traditional shortest-path approaches, this framework incorporates:

*  Elevation and slope
*  Terrain / land cover
*  Population trade-offs
*  Local connection strategies

The result is a more realistic and cost-sensitive routing model, particularly suited for infrastructure planning (e.g., fiber deployment).

---

##  Example Output


<p align="center">
  <img src="visual results/Terrain-aware cost surface/ResultEx1.png" width="600"/>
</p>

<p align="center">
Terrain-aware routing (pink) avoids high-cost regions compared to baseline routing (green).
</p>
<p align="center">
(red indicates lower terrain cost)
</p>



##  Key Idea

Instead of minimizing distance:

```
minimize(distance)
```

we optimize:

```
minimize(distance × terrain × slope × context)
```

This transforms routing from a purely geometric problem into a **multi-factor geospatial optimization problem**.

---

##  Core Contributions

### 1. Terrain-Aware Cost Model

* Edge costs incorporate:

  * terrain difficulty
  * elevation slope
  * optional population weighting
* Modular and extensible penalty design

---

### 2. Elevation-Driven Penalization

* Slope computed from elevation differences
* Terrain difficulty influences routing decisions
* Enables avoidance of physically expensive paths

---

### 3. Grid-Based Local Access Strategy

* Connects off-network points (POIs) to the road graph
* Uses a structured local grid instead of naive nearest-node linking
* Includes fallback strategies for robustness

## Local Connection Strategy

<p align="center">
  <img src="visual results/Grid-based local connection/GridRepresentation.png" width="500"/>
</p>

<p align="center">
Structured grid-based connection of off-network points to the road graph.
</p>

---

### 4. End-to-End Routing Pipeline

* POI integration
* Cost computation
* Graph construction
* Path optimization
* Evaluation vs baseline

---

##  Architecture

```
Inputs:
    - Road network
    - Points of interest (POIs)
    - Terrain data
    - Elevation data

Pipeline:
    1. Preprocess graph
    2. Compute edge penalties
    3. Connect POIs via grid strategy
    4. Run shortest path (weighted)
    5. Evaluate results

Outputs:
    - Optimized routes
    - Cost metrics
    - Baseline comparison
```

---

##  Performance Summary

| Metric              | Change |
|--------------------|--------|
| Penalized length   | ↓ 1.7% |
| Total penalization | ↓ 9.3% |
| Curvature penalty  | ↓ 30.3% |
| Population impact  | ↑ 8.6% |

---
##  Demo

This repository includes a **fully reproducible synthetic demo**.

Run:

```bash
python demo/synthetic_case_study.py
```

Example output:

```
Best path: ['A', 'C']
```

---

##  Example Insight

| Path      | Distance | Terrain Cost          | Final Cost |
| --------- | -------- | --------------------- | ---------- |
| A → B → C | shorter  | high (forest + slope) | higher     |
| A → C     | longer   | low (urban)           | lower      |

 The model selects **A → C**, showing more realistic routing behavior.

---

##  Project Structure

```
terrain-aware-fiber-routing/
├── docs/           # Methodology and design
├── pseudocode/     # Algorithm descriptions
├── demo/           # Runnable simplified examples
├── data/           # Data specification (no real data)
```

---

##  Confidentiality Notice

This repository is a **sanitized public version** of a larger system.

### Included:

* methodology
* pseudocode
* simplified implementations
* synthetic experiments

### Excluded:

* production code
* internal datasets
* proprietary integrations
* real infrastructure data

---

##  Installation

```bash
pip install -r requirements-demo.txt
```

---

##  Limitations

* Synthetic data only
* Simplified terrain modeling
* No large-scale optimization
* No real-world calibration

---

##  Future Work

* Real terrain raster integration
* Multi-objective optimization
* Scalability improvements
* Integration with real GIS pipelines

---

##  Author

Developed as part of a geospatial network optimization project.

**Focus areas:**

* Geospatial algorithms
* Network routing
* Terrain modeling
* Infrastructure optimization

---

##  License

MIT License
