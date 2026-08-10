# Sensory Friendly Routing Backend

FastAPI backend for the US1.2 crowd-avoidance prototype. It reads the FIT5120
MySQL RDS contract, estimates edge-level crowding, and compares the shortest
walking route with a lower-crowd alternative.

## Setup and run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Before running locally, set the RDS connection environment variables. Obtain
the real read-only values through AWS Secrets Manager; do not commit them.

```powershell
$env:MYSQL_HOST = "your-rds-endpoint.amazonaws.com"
$env:MYSQL_PORT = "3306"
$env:MYSQL_DATABASE = "fit5120_data"
$env:MYSQL_USER = "fit5120_app"
$env:MYSQL_PASSWORD = "<secret>"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:5173,https://dpevp4238kw5k.cloudfront.net,https://calmpath-tp10.netlify.app"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Use [.env.example](.env.example) as the variable reference. In ECS, inject the
same values from AWS Secrets Manager. The frontend must never connect to RDS.
The contract identifies RDS as private; run the API from an approved ECS/VPC
network path or a team-provided secure tunnel, not an ordinary public desktop
connection.
Open <http://127.0.0.1:8000/docs> to use the interactive API documentation.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service information |
| `GET` | `/api/v1/health` | Confirms loaded data counts |
| `GET` | `/api/v1/edges/{edge_id}?weekday_index=0&local_hour=12&use_current=true` | Returns an edge and its current/historical crowd estimate |
| `POST` | `/api/v1/routes/compare` | Compares shortest and crowd-aware walking routes |

Example edge request:

```text
GET /api/v1/edges/edge_051a94ac5e0e70bf844cc3b0?weekday_index=0&local_hour=7&use_current=true
```

Example route request (coordinates are snapped to the nearest routing node):

```json
{
  "origin": {"latitude": -37.813, "longitude": 144.963},
  "destination": {"latitude": -37.820, "longitude": 144.950},
  "travel_time": "2026-08-10T12:00:00+10:00"
}
```

The frontend supplies coordinates only. `origin_node_id` and
`destination_node_id` in the response are calculated by the backend and are
included only for debugging and traceability.

The response includes ordered `segments` so the frontend can colour each
GeoJSON LineString as `LOW`, `MEDIUM`, `HIGH`, or `UNKNOWN`. Every segment has
an explicit one-based `sequence`, `crowd_level`, crowd-derived `sensory_level`,
and `limited_data`; clients do not need to infer these values. GeoJSON coordinates
remain in standard `[longitude, latitude]` order. Each segment separates an
evidence-backed `crowd_score` from an optional unknown-data `routing_penalty`.

`crowd_exposure` is the known-distance-weighted mean crowd count and
`data_coverage_ratio` is known distance divided by total route distance. The
separate `routing_crowd_cost` is a distance-scaled penalty in seconds used by
route search; it is not a measured pedestrian count. `current_data_used` is
`true` only when at least one segment in the response actually uses a live
observation. A past/future trip, or a current request that falls back entirely
to historical/unknown data, returns `false`.

The frontend should branch on `recommendation_status`, not parse the English
`recommendation_note`. Possible values are `LOWER_CROWD`,
`SHORTEST_ALREADY_BEST`, `INSUFFICIENT_DATA`, and `NO_ALTERNATIVE`.

Every route also returns:

- `crowd_level`: route-level `LOW`, `MEDIUM`, or `HIGH`, or null for limited data;
- `sensory_level`: currently the same level, with
  `sensory_level_basis: "PEDESTRIAN_CROWD_ONLY"`;
- `limited_data`: true when known-distance coverage is below 0.60;
- `minimum_required_coverage_ratio`, `known_distance_m`, and
  `unknown_distance_m` so the frontend does not need hidden rules.

## Crowd scoring rule

The routing graph is loaded from `backend_routing_nodes` and
`backend_routing_edges`. Historical values come from
`backend_edge_hourly_patterns`. For a trip departing now, the API calculates
fresh edge observations from `clean_pedestrian_minute` joined via
`backend_sensor_edge_map`; it deliberately does not use
`backend_edge_sensory_context_current`, because that materialised table is not
refreshed by the 15-minute minute-count job.

For every route edge, the API uses a `CURRENT` + `OBSERVED` live `crowd_count`
when one is available; otherwise it falls back to the historical `mean_count`
for the requested weekday/hour. If neither source has data, the API reports
the edge as unknown and uses a prototype penalty of 75 for routing. Unknown is
never interpreted as low crowding.

When several current sensors map to one edge, the highest count is used and the
segment reports `aggregation_method: "maximum"`. `evaluated_at` is the backend
evaluation time, while `observed_at` is the actual source observation time.

When either route has below 60% known-distance crowd coverage, the API returns an
insufficient-coverage note instead of claiming that the recommended route is
genuinely quieter.

## Units and crowd levels

Live records are counts for one observed minute. Historical patterns are means
of hourly totals and are divided by 60 before use. Consequently segment scores
and `crowd_exposure` use `pedestrians_per_minute`, with a minimum of zero and no
fixed maximum.

The `provisional-dmp-v1` thresholds are:

```yaml
LOW:    <= 50 pedestrians/minute
MEDIUM: <= 150 pedestrians/minute
HIGH:   > 150 pedestrians/minute
```

The thresholds match the current published data-package rule and remain
prototype values requiring team and mentor calibration.

## CloudFront deployment requirement

FastAPI now accepts JSON POST preflight requests from
`https://calmpath-tp10.netlify.app`. The CloudFront behaviour for `/api/v1/*`
must separately allow POST and OPTIONS, forward the CORS request headers, and
avoid caching POST responses. This infrastructure setting is outside this
backend repository.

## Local US1.2 tests

The automated suite uses an in-memory graph and does not connect to RDS:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

See [RDS_INTEGRATION.md](RDS_INTEGRATION.md) for the tables, joins, and
freshness rules. The congestion thresholds are prototype values, not official
Melbourne congestion standards.
