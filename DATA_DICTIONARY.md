# US1.2 data dictionary

This document describes the CSV package used by the sensory-friendly routing
prototype. The data files currently live in
`D:\monash\backend-csv-data-package\backend-csv-data-package\backend`.

## Relationship overview

```text
routing_nodes (node_id)
  └─< routing_edges (from_node_id, to_node_id, edge_id)
        ├─< edge_hourly_patterns (edge_id, weekday_index, local_hour)
        ├──  edge_sensory_context_current (edge_id)
        └─< sensor_edge_map (location_id, edge_id)

landmark_node_map (landmark_id, node_id) ──> routing_nodes
refuge_candidates (landmark_id) ───────────> landmark_node_map
```

## Table reference

| CSV | Row represents | Key | Relationships | US1.2 use |
| --- | --- | --- | --- | --- |
| `routing_nodes.csv` | One walkable-network vertex | `node_id` | Referenced by `routing_edges.from_node_id` and `.to_node_id`; optionally by `landmark_node_map.node_id` | Required for graph routing and coordinate lookups. |
| `routing_edges.csv` | One directed network segment (marked `is_bidirectional` where travel is also allowed in reverse) | `edge_id` | References two routing nodes; parent of the edge-based tables below | Required: route graph, walking cost, geometry, street labels. |
| `edge_hourly_patterns.csv` | Historical pedestrian count for one edge, weekday and local hour | (`edge_id`, `weekday_index`, `local_hour`) | `edge_id` → `routing_edges.edge_id` | Required fallback crowd estimate. Use `mean_count`; retain sample and min/max values for confidence/explanation. |
| `edge_sensory_context_current.csv` | Latest observation/context for one edge | `edge_id` | `edge_id` → `routing_edges.edge_id` | Required live input. Use only trustworthy observed values; it also includes copied display geometry/labels. |
| `sensor_edge_map.csv` | Mapping of a pedestrian sensor location to a nearby edge | (`location_id`, `edge_id`) | `edge_id` → `routing_edges.edge_id` | Not required for the first route-comparison API; needed when ingesting/diagnosing sensor data. |
| `landmark_node_map.csv` | Snap of a landmark to a routing node | `landmark_id` | `node_id` → `routing_nodes.node_id` | Optional origin/destination lookup by landmark name. |
| `refuge_candidates.csv` | A landmark assessed as a possible quiet refuge | `landmark_id` | `landmark_id` → `landmark_node_map.landmark_id` | Out of scope for US1.2; use for a later refuge feature. |

## Important fields

### `routing_edges.csv`

- `from_node_id`, `to_node_id`: graph endpoints.
- `base_walk_cost_seconds`: shortest-path weight for the conventional route.
- `length_m`, `geometry_geojson`, `street_name`, `between_street_1`,
  `between_street_2`: map/UI metadata.
- `is_bidirectional`: reverse traversal must be added by the routing service
  when this is `true`.
- `quality_status`, `quality_flags`, `network_version`, `lineage_id`: data
  validation/provenance fields, not routing weights.

### `edge_hourly_patterns.csv`

- `weekday_index` is Monday = `0`; `weekday_name` is its display label.
- `local_hour` is the local 24-hour hour (for example `12` for 12:00–12:59).
- `mean_count` is the prototype historical crowd value. `sample_count`,
  `minimum_count`, `maximum_count`, and `contributing_sensor_count` communicate
  how much evidence supports it.

### `edge_sensory_context_current.csv`

- `crowd_count`, `crowd_level`, and `sensory_indicator` describe the current
  state only when an observation is usable.
- Treat `observation_status = CURRENT` and `coverage_status = OBSERVED` as a
  usable live observation. Treat `STALE`, `UNAVAILABLE`, and
  `NO_RECENT_OBSERVATION` as unavailable for a current score and fall back to
  the hourly pattern.
- `as_of` and `source_observed_at` should be returned to clients so they can
  show freshness.
- `contributing_location_ids`, `contributing_sensor_count`, and `quality_flags`
  explain provenance and coverage.

## Verified package facts (2026-08-07)

- `routing_edges` has 76,845 edges and every edge endpoint exists in
  `routing_nodes`.
- `edge_sensory_context_current` has exactly one row per edge and all its
  `edge_id` values exist in `routing_edges`.
- Its availability is sparse: 34 `CURRENT`, 63 `STALE`, 1 `UNAVAILABLE`, and
  76,747 `NO_RECENT_OBSERVATION` rows. An empty `crowd_count` means **unknown**,
  not low crowding.
- `edge_hourly_patterns` has 16,159 rows for 99 edges. Its compound key has no
  duplicates, but most network edges have no historical pattern.
- `sensor_edge_map` covers 124 unique edges (134 mappings); its compound key
  has no duplicates.
- `landmark_node_map` has 242 landmark mappings; six point to nodes absent
  from this network version. The API must reject or flag those landmarks rather
  than routing from them.
- All 38 `refuge_candidates` have a matching landmark mapping.

## Minimum US1.2 read set and score source

The first implementation should load four files: `routing_nodes.csv`,
`routing_edges.csv`, `edge_hourly_patterns.csv`, and
`edge_sensory_context_current.csv`.

For each edge in a candidate route:

1. Use the current `crowd_count` only when the current row is observed and
   current.
2. Otherwise use `mean_count` for the requested weekday/hour, if present.
3. If neither source has a value, mark the edge as `UNKNOWN` and expose that
   uncertainty in the API response; do not silently score it as zero.

The initial congestion labels can use prototype thresholds (`LOW < 50`,
`MEDIUM 50–99`, `HIGH >= 100`) until the team validates a domain-specific
model. Those are product-development thresholds, not official congestion
standards.
