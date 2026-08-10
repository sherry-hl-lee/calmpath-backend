# RDS integration

This backend uses the FIT5120 MySQL RDS contract, database `fit5120_data`.
Credentials are supplied at runtime through environment variables or AWS
Secrets Manager and must never be committed.

| Backend need | RDS table(s) | Runtime behaviour |
| --- | --- | --- |
| Routing graph | `backend_routing_nodes`, `backend_routing_edges` | Loaded into memory at API startup for route search. |
| Historical crowd | `backend_edge_hourly_patterns` | Looked up by `edge_id`, Melbourne `weekday_index`, and `local_hour`. |
| Current crowd | `clean_pedestrian_minute`, `backend_sensor_edge_map` | Refreshed per current-time request. Latest count per sensor is joined to its published edge mapping. |

## Current crowd rule

The materialised `backend_edge_sensory_context_current` table is not refreshed
by the 15-minute pipeline job, so this API does not use it for live scoring.

For every mapped sensor, the API selects its latest minute observation and
recalculates freshness against `UTC_TIMESTAMP()`:

- up to 30 minutes old: `CURRENT`;
- more than 30 and up to 60 minutes old: `STALE`;
- older, absent, or unmapped: unavailable.

If more than one current sensor maps to an edge, the API uses the arithmetic
mean of their `count_total` values. This avoids silently double-counting nearby
sensors, but remains a prototype aggregation rule requiring team approval.

Live observations are used only when the requested departure time is within
15 minutes of now. Past or future trips use historical patterns, because a
current sensor reading is not a prediction.

## Important limitation

The RDS contract contains 85,615 routing edges but only 124 published
sensor-to-edge mappings. Historical patterns therefore do not cover every
routing edge. `UNKNOWN` must not be displayed as low crowding; the existing
score of 75 is a temporary routing penalty, not a measured pedestrian count.

The API returns `crowd_exposure` from known observations/patterns only, while
`routing_crowd_cost` also contains the unknown penalty used in route search.
When either compared route has under 60% known edge coverage, the API reports
that the data is insufficient for a reliable low-crowd recommendation.
