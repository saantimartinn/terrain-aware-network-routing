# Validation Results

## Experiment Setup

Comparison between:

* Baseline routing (distance-only)
* Terrain-aware routing (multi-factor cost)

---

## Actual Results

| Metric              | Value           |
| ------------------- | --------------- |
| Edges               | 2064 (+4.3%)    |
| Physical Length     | 222,113 (+1.9%) |
| Penalized Length    | 315,599 (-1.7%) |
| Total Penalization  | 93,485 (-9.3%)  |
| Slope Penalty       | 66,523 (-8.8%)  |
| Curvature Penalty   | 7,521 (-30.3%)  |
| Surface Penalty     | ~ (≈0%)         |
| Population Affected | 6,794 (+8.6%)   |
| Length_pop          | 257,455 (-3.4%) |
| Ratio               | 1.421 (-3.5%)   |

---

## Key Insights

* Terrain-aware routing reduces overall penalization significantly
* Strong improvement in curvature optimization
* Slight increase in physical length is compensated by better terrain selection
* Increased population coverage suggests better infrastructure relevance

---

## Interpretation

The model successfully trades off:

* **shortest distance** vs
* **lowest physical + environmental cost**

This results in more realistic and deployable routing solutions.
