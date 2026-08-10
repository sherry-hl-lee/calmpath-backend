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
| `GET` | `/health` | Confirms loaded data counts |
| `GET` | `/edges/{edge_id}?weekday_index=0&local_hour=12` | Returns an edge and its current/historical crowd estimate |
| `POST` | `/routes/compare` | Compares shortest and crowd-aware walking routes |

Example edge request:

```text
GET /edges/edge_051a94ac5e0e70bf844cc3b0?weekday_index=0&local_hour=7
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

The response includes route edge IDs, GeoJSON LineString geometry, walking
time, evidence-backed `crowd_exposure`, and data coverage fields. The separate
`routing_crowd_cost` includes the temporary unknown-data penalty used during
search; it is not a measured pedestrian count. `current_data_used` is `true`
only for a departure time close to now; a past or future planned trip uses
historical patterns instead.

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

When either route has below 60% known crowd coverage, the API returns an
insufficient-coverage note instead of claiming that the recommended route is
genuinely quieter.

See [RDS_INTEGRATION.md](RDS_INTEGRATION.md) for the tables, joins, and
freshness rules. The congestion thresholds are prototype values, not official
Melbourne congestion standards.
