# US1.1 merge notes

This package is based on the downloaded backend archive at commit:

```text
ce1a464f65bed1f175be8eb75f411b587b6d494b
```

## Preserved behaviour

- `GET /health`
- `GET /api/v1/refuges/nearby`
- `GET /api/v1/refuges/address`
- current `RDS_HOST`, `RDS_PORT`, `RDS_DATABASE`, `RDS_USER`, `RDS_PASSWORD`
- existing localhost, GitHub Pages and Netlify CORS origins

## Added behaviour

- `GET /api/v1/routes`
- alternative walking route geometry;
- `High`, `Low`, and `Limited Data` sensory indicators;
- pedestrian sensor coverage and count score;
- nearby metropolitan train/tram access points;
- `DATA_SOURCE=fake/rds` runtime provider selection;
- deterministic local fake routes covering all three sensory indicators;
- US1.1 API, scoring, validation and CORS tests.

The frontend-facing endpoint is `GET`, so the current CloudFront method and
query-string configuration can remain unchanged.

## Deployment requirement

Add `ORS_API_KEY` to the ECS task definition as a protected secret/environment
value and explicitly set `DATA_SOURCE=rds`. Do not commit secrets. Existing RDS
variables remain unchanged. The Docker
image includes Amazon's global RDS CA bundle and sets `RDS_SSL_CA` so the MySQL
client verifies the server certificate and hostname.

## Database boundary

The existing refuge APIs still query MySQL RDS. US1.1 now queries active
locations from `clean_sensor_locations` and the most recent count for each
location from `clean_pedestrian_minute`. Stale or unavailable counts result in
`Limited Data`.

OpenRouteService remains the temporary route generator. Its geometry is matched
to sensor coordinates for the MVP. A future version can match the geometry to
`backend_routing_edges.edge_id` and use `backend_sensor_edge_map` for more
reliable edge-level scoring. Victorian GTFS remains the external source for
tram/train stops because they are not published to RDS.

## Verification

```text
35 tests passed
```

The tests cover existing health/refuge/address behaviour and the new US1.1 API,
CBD validation, CORS, High/Low scoring, Limited Data behaviour, and the RDS
sensory query/cache mapping. They also verify that fake mode uses only in-memory
providers and that rds mode constructs the real providers. Live end-to-end
calls still require a valid ORS key, RDS network access and access to the
official GTFS feed.
