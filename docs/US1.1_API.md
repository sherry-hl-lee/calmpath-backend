# FIT5120 CalmPath US1.1 API

## Scope

US1.1 returns one or more walking route options to a destination inside
Melbourne CBD. Each route includes:

- `High` or `Low` sensory indicator when pedestrian sensor coverage is adequate;
- `Limited Data` when coverage or counts are insufficient;
- route geometry for the frontend map;
- nearby metropolitan tram stops and train stations.

The endpoint is deliberately a `GET` request so it works with the project's
current CloudFront configuration (`GET`, `HEAD`, `OPTIONS`) and forwarded query
strings.

## Request

```text
GET /api/v1/routes
  ?origin_latitude=-37.8183
  &origin_longitude=144.9671
  &destination_latitude=-37.8102
  &destination_longitude=144.9628
```

The origin may be outside the CBD. The destination must fall within the
backend's Melbourne CBD bounding box.

## Successful response

```json
{
  "routes": [
    {
      "id": "route-1",
      "distance_m": 900.0,
      "duration_s": 700.0,
      "sensory_indicator": "Low",
      "sensory_score": 350.0,
      "sensor_coverage": 0.6,
      "sensors_used": 3,
      "nearby_transport": [
        {
          "id": "station-1",
          "name": "Melbourne Central",
          "type": "train",
          "latitude": -37.8102,
          "longitude": 144.9628,
          "distance_to_route_m": 50.0
        }
      ],
      "geometry": {
        "type": "LineString",
        "coordinates": [[144.9671, -37.8183], [144.9628, -37.8102]]
      }
    }
  ]
}
```

## MVP sensory rule

1. Sample each generated route every 80 metres.
2. Find active pedestrian sensors within 120 metres of the route.
3. Calculate the fraction of route samples covered by a nearby sensor.
4. Coverage below 20% returns `Limited Data`.
5. Otherwise calculate the mean of the latest fresh `count_total` values.
6. A score of at least the configured threshold (600 by default) is `High`; a
   lower score is `Low`.

All distances and thresholds are environment-configurable. They are MVP
engineering assumptions, not medical definitions of sensory safety.

## Runtime data boundary

`DATA_SOURCE` selects the providers without changing the endpoint or response
schema:

- `fake`: deterministic local route, sensory and transport providers; no RDS,
  ORS or GTFS access. The three demo routes exercise `High`, `Low`, and
  `Limited Data`.
- `rds`: OpenRouteService geometry, RDS sensor/count data, and official
  Victorian GTFS access points.

Direct local execution defaults to `fake`. The Docker image defaults to `rds`,
and ECS must explicitly configure `DATA_SOURCE=rds`. Fake data must never be
presented as real Melbourne observations.

Walking geometry is currently supplied by OpenRouteService and requires an
`ORS_API_KEY` injected into ECS. Active sensor coordinates come from
`clean_sensor_locations`; latest counts come from
`clean_pedestrian_minute`, joined by `location_id`. The query uses only rows
where `expected_active = 1` and picks the newest `observed_at_utc` for each
sensor. Results are cached in-process for 60 seconds by default. A latest count
older than 30 minutes is treated as missing, which can make the route
`Limited Data`.

The default route-provider endpoint is
`https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson`.
It can be overridden through `ORS_BASE_URL` without changing application code.

For this version, route samples are matched directly to nearby sensor
coordinates. The available `backend_routing_edges` and
`backend_sensor_edge_map` tables are suitable for a later server-side
route-to-edge matching improvement, but the materialised current sensory table
is not used because it is not rebuilt by the 15-minute refresh.

Train and tram access points come from the official Victorian GTFS Schedule;
they are not currently published to RDS.

The default score threshold is an MVP product assumption. The database team
should confirm the measurement window represented by recent `count_total`
before it is treated as a calibrated crowd threshold.

## Frontend integration

Use the existing HTTPS API base:

```text
https://dpevp4238kw5k.cloudfront.net
```

The frontend should render `geometry` as a GeoJSON LineString, show the sensory
indicator on each route option, and place markers from `nearby_transport`.
The frontend does not need to know which runtime mode produced the response.
