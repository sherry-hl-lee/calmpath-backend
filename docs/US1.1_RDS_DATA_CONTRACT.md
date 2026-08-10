# US1.1 RDS data contract

Contract received from the database team and implemented for the MVP:

- `clean_sensor_locations`: sensor coordinates and `expected_active`;
- `clean_pedestrian_minute`: recent `count_total`, refreshed every 15 minutes;
- join key: `location_id`.

The backend selects the latest `observed_at_utc` row for each active sensor.
It does not need database write access.

Available but not yet used by the MVP implementation:

- `clean_pedestrian_hourly` for historical patterns;
- `backend_routing_nodes` and `backend_routing_edges` for in-database routing;
- `backend_sensor_edge_map` for sensor-to-edge association;
- `backend_edge_hourly_patterns` for historical edge patterns;
- `backend_edge_sensory_context_current`, because it is not currently rebuilt
  by the 15-minute refresh.

OpenRouteService remains the route generator. Route samples are matched to
sensor coordinates in application code. The next routing-data iteration should
map ORS geometry to `backend_routing_edges.edge_id` server-side.

Tram and train stops are not published to RDS, so the official Victorian GTFS
feed remains the runtime source.

One calibration item remains: confirm the exact measurement interval/unit of
`clean_pedestrian_minute.count_total` before finalising the default High/Low
threshold.
