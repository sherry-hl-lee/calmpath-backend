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

If more than one current sensor maps to an edge, the API uses the maximum
`count_total`. For crowd avoidance, this conservative prototype rule prevents
a quiet sensor from masking a busy part of the same routing edge. Segment
responses expose `sensor_count` and `aggregation_method: "maximum"`.

Live observations are used only when the requested departure time is within
15 minutes of now. Past or future trips use historical patterns, because a
current sensor reading is not a prediction.

## Count unit and thresholds

`clean_pedestrian_minute.count_total` is a one-minute count. Historical
`backend_edge_hourly_patterns.mean_count` is the mean of one-hour totals, so the
backend divides it by 60 before classification, route search, or exposure
calculation. All evidence-backed API scores therefore use
`pedestrians_per_minute`.

The route and segment levels use the versioned prototype rule
`provisional-dmp-v1`:

| Level | Pedestrians per minute |
| --- | ---: |
| `LOW` | `<= 50` |
| `MEDIUM` | `> 50` and `<= 150` |
| `HIGH` | `> 150` |

These thresholds match the published data-package rule but still require team
and mentor calibration before production. Historical hourly averages smooth
short minute-level peaks, so historical routes will produce fewer `HIGH`
segments than live observations.

## Important limitation

The RDS contract contains 85,615 routing edges but only 124 published
sensor-to-edge mappings. Historical patterns therefore do not cover every
routing edge. `UNKNOWN` must not be displayed as low crowding; the existing
score of 75 is a temporary routing penalty, not a measured pedestrian count.

The API returns a distance-weighted `crowd_exposure` from known observations or
patterns only. Coverage is also measured by known distance rather than edge
count. `routing_crowd_cost` is the distance-scaled crowd penalty in seconds and
may include the unknown penalty used in route search; it is not a pedestrian
count. When either compared route has under 60% known-distance coverage, the
API returns `recommendation_status: "INSUFFICIENT_DATA"`.

Route-level `crowd_level` and `sensory_level` are null when coverage is below
60%. The current `sensory_level` is explicitly crowd-derived only; RDS does not
contain independent noise, lighting, or construction measurements.
