# Sensory Friendly Routing Backend

FastAPI backend for the US1.2 crowd-avoidance prototype. It reads the supplied
Melbourne routing CSVs, estimates edge-level crowding, and compares the
shortest walking route with a lower-crowd alternative.

## Setup and run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> to use the interactive API documentation.

The required CSV files are included in `data/`. To point the app at another
directory, set the `DATA_DIR` environment variable before starting Uvicorn.

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
time, total estimated crowd exposure, and the number of edges with unknown
crowd data.

## Crowd scoring rule

For every route edge, the API uses a `CURRENT` + `OBSERVED` live `crowd_count`
when one is available; otherwise it falls back to the historical `mean_count`
for the requested weekday/hour. If neither source has data, the API reports
the edge as unknown and uses a prototype penalty of 75 for routing. Unknown is
never interpreted as low crowding.

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for the CSV keys, joins, and data
limitations. The congestion thresholds are prototype values, not official
Melbourne congestion standards.
