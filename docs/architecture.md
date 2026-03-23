# Architecture

## Inputs

- Road network (graph)
- Points of interest (POIs)
- Terrain classification
- Elevation data
- Population density (optional)

## Pipeline

1. Map POIs to network
2. Compute edge costs:
   - base length
   - terrain penalty
   - slope penalty
3. Build routing graph
4. Compute shortest paths
5. Evaluate results

## Outputs

- Connected network
- Route costs
- Comparison metrics