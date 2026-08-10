# CalmPath Backend

FastAPI backend for the US1.2 crowd-avoidance prototype. It reads the FIT5120
MySQL RDS contract, estimates edge-level crowding, and compares the shortest
walking route with a lower-crowd alternative.

## Setup and run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For local frontend integration, select the deterministic fake repository. It
uses the same RoutingService, endpoints, request schema, response schema, and
crowd-scoring code as RDS mode, but never opens a MySQL connection. Its values
are synthetic historical patterns, so fake responses intentionally report
`current_data_used: false` and must not be presented as real-time data:

```powershell
$env:DATA_SOURCE = "fake"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

For ECS, explicitly select RDS and inject the real read-only values through AWS
Secrets Manager; do not commit them:

```powershell
$env:DATA_SOURCE = "rds"
$env:RDS_HOST = "your-rds-endpoint.amazonaws.com"
$env:RDS_PORT = "3306"
$env:RDS_DATABASE = "fit5120_data"
$env:RDS_USER = "fit5120_app"
$env:RDS_PASSWORD = "<secret>"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:5173,https://fit5120-2026s2-tp10.github.io,https://dpevp4238kw5k.cloudfront.net,https://calmpath-tp10.netlify.app"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Use [.env.example](.env.example) as the variable reference. In ECS, inject the
RDS values from AWS Secrets Manager. The frontend must never connect to RDS.
The contract identifies RDS as private; run the API from an approved ECS/VPC
network path or a team-provided secure tunnel, not an ordinary public desktop
connection.
Open <http://127.0.0.1:8000/docs> to use the interactive API documentation.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Stable service liveness check |
| `GET` | `/api/v1/refuges/nearby` | Finds nearby low-sensory refuges |
| `GET` | `/api/v1/refuges/address` | Resolves a selected refuge address |
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

The application itself can also be smoke-tested without RDS:

```powershell
$env:DATA_SOURCE = "fake"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then call `GET http://127.0.0.1:8000/api/v1/health` and
`POST http://127.0.0.1:8000/api/v1/routes/compare` with the request shown above.

See [RDS_INTEGRATION.md](RDS_INTEGRATION.md) for the tables, joins, and
freshness rules. The congestion thresholds are prototype values, not official
Melbourne congestion standards.

## Refuge and address APIs

The service also retains the existing refuge and reverse-geocoding APIs from the
main CalmPath backend.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the FastAPI documentation at `http://127.0.0.1:8000/docs`.

Before running against the deployment database, provide the RDS connection
settings through environment variables. Do not commit real passwords, secrets,
API keys, or private paths.

## Refuge data source

Runtime refuge data comes from the MySQL RDS table
`backend_refuge_candidates`. The backend no longer reads the bundled CSV and no
longer calls the City of Melbourne Street API.

### Nearby refuge data contract

`GET /api/v1/refuges/nearby` queries only rows where
`is_refuge_candidate = 1`. The backend calculates Haversine distance from the
request coordinates, filters by `radius_m`, and sorts by ascending distance.

| RDS field | API field | Rule |
| --- | --- | --- |
| `landmark_id` | `id` | Direct mapping |
| `feature_name` | `name` | Direct mapping |
| `sub_theme` | `type` | Park/Garden/Reserve becomes `park`; Library becomes `library` |
| `latitude` | `latitude` | Refuge coordinates |
| `longitude` | `longitude` | Refuge coordinates |
| Backend Haversine result | `distance_m` | Rounded to two decimal places |

### Address data contract

`GET /api/v1/refuges/address` receives the selected refuge's `latitude` and
`longitude`. It queries the same RDS table and only uses rows where
`address_match_status = 'MATCHED'`.

| RDS field | API field |
| --- | --- |
| `address` | `address` |
| `address_latitude` | `latitude` |
| `address_longitude` | `longitude` |
| `address_distance_m` | `match_distance_m` |
| `address_source` | `source` |

Address matching is generated by the data pipeline. The maximum stored address
matching distance is 319 metres. The backend does not perform live geocoding or
call the City of Melbourne Street API at runtime.

## Project structure

```text
app/
  api/routes/    HTTP endpoints
  schemas/       request and response data models
  services/      business logic
  models/        database models
tests/           automated tests
docs/api/        short API contracts
```
