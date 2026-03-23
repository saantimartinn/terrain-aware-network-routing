# Methodology

## Edge Cost Model

Each edge cost is defined as:

cost = length × terrain_factor × slope_factor × population_factor

## Terrain Factor

Assigned based on land type:
- urban → low penalty
- forest → medium
- water → high

## Slope Factor

Derived from elevation difference:

slope = Δelevation / distance

Higher slope → higher cost

## Population Factor

Optional trade-off:
- prefer routes near populated areas
- or avoid them depending on objective