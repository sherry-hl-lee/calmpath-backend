# FIT5120 CalmPath US2.1 API

## 1. Scope

US2.1 supports:

1. Finding nearby refuges from Shogo's `refuge_candidates.csv` using the user's location and search radius.
2. Looking up the nearest City of Melbourne street address after the user selects a refuge.

This implementation does not use a database, Google Geocoding, Google Maps, or an external API key.

The nearby search uses the backend's Haversine distance calculation. The nearby endpoint does not call the address API and does not look up an address for every search result.

## 2. `GET /api/v1/refuges/nearby`

### Request

```text
GET /api/v1/refuges/nearby?latitude=-37.8136&longitude=144.9631&radius_m=5000
```

Query parameters:

| Parameter | Type | Description |
| --- | --- | --- |
| `latitude` | float | User latitude, from `-90` to `90` |
| `longitude` | float | User longitude, from `-180` to `180` |
| `radius_m` | float | Search radius, greater than `0` metres |

The data path is configured through `REFUGE_DATA_PATH`. For example:

```dotenv
# REFUGE_DATA_PATH=app/data/refuge_candidates.csv
```

Only records with `is_refuge_candidate=true` are included.

### `type` mapping

The API `type` is mapped only from the CSV `sub_theme` field:

| `sub_theme` | `type` |
| --- | --- |
| `Informal Outdoor Facility (Park/Garden/Reserve)` | `park` |
| `Library` | `library` |

The implementation does not map `theme` to `type` and does not add other types.

### Successful response

The top-level response is a bare array. Each item contains:

```json
[
  {
    "id": "ea40efc1f181c0943d97b001",
    "name": "Alexandra Gardens",
    "type": "park",
    "latitude": -37.8206051404251,
    "longitude": 144.971796067365,
    "distance_m": 1214.36
  }
]
```

Field mapping:

| CSV field | API field |
| --- | --- |
| `landmark_id` | `id` |
| `feature_name` | `name` |
| `sub_theme` | `type`, converted using the mapping above |
| `latitude` | `latitude`, converted to float |
| `longitude` | `longitude`, converted to float |
| Backend Haversine result | `distance_m` |

The nearby response does not include `address`.

## 3. `GET /api/v1/refuges/address`

This endpoint is called only after the user selects a refuge.

### Request

```text
GET /api/v1/refuges/address?latitude=-37.795&longitude=144.958
```

Query parameters:

| Parameter | Type | Description |
| --- | --- | --- |
| `latitude` | float | Selected refuge latitude, finite and from `-90` to `90` |
| `longitude` | float | Selected refuge longitude, finite and from `-180` to `180` |

The request does not accept a custom address lookup radius. The backend uses a fixed maximum matching distance of `200 m`.

The City of Melbourne query uses:

- Geographic field: `geo_point_2d`
- Centre point: `POINT(longitude latitude)`
- `within_distance(..., 200 m)`
- `order_by distance(...) asc`
- `limit=1`

Query parameters are passed through `httpx`'s `params` argument, which handles URL encoding. The code does not manually concatenate unencoded query parameters.

### Successful response

```json
{
  "address": "61 Royal Parade Parkville",
  "latitude": -37.79516121,
  "longitude": 144.95776822,
  "match_distance_m": 42.5,
  "source": "City of Melbourne Street Addresses"
}
```

### Error responses

Errors use FastAPI's standard format:

```json
{
  "detail": "Description"
}
```

| Status | Situation |
| --- | --- |
| `422` | Invalid, non-finite, or out-of-range coordinates |
| `404` | A refuge may exist, but no valid street address is within `200 m`; this does not mean the refuge does not exist |
| `429` | The per-client-IP address request limit was reached; the response includes `Retry-After` |
| `503` | City of Melbourne timeout, connection failure, invalid JSON, upstream 5xx, or upstream rate limiting |

An upstream `429` is not followed by an aggressive automatic retry. If the upstream provides `Retry-After`, it is forwarded to the caller. The system does not perform unlimited retries or background polling.

Address lookup protections:

- Fixed lookup radius of `200 m`
- In-memory cache with a 10-minute TTL and a maximum of 256 entries
- Cache key based on rounded latitude and longitude
- Each client IP can make 30 address requests per 60 seconds by default
- At most 4 concurrent City of Melbourne requests
- Upstream timeout of no more than 5 seconds
- Custom `X-Forwarded-For` values are not trusted
- The cache does not write to a database or persist address files

## 4. Frontend call sequence

1. Call `/api/v1/refuges/nearby` when the user searches.
2. Display the nearby results without calling the address endpoint in a result loop.
3. When the user clicks or selects a refuge, call `/api/v1/refuges/address` with that refuge's latitude and longitude.
4. Trigger at most one address request per selection; reuse a successful result already available on the current page.
5. Show a friendly message for `429`, timeout, or `503`; do not create an automatic frontend retry loop.

## 5. Data source, licence, and limitations

Address data source: City of Melbourne Street Addresses Open Data.

Dataset API:

<https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/street-addresses/records>

Use of this dataset should follow the CC BY licence shown on the source page, including appropriate attribution. Address data may contain approximate or older addresses, or a match that does not exactly represent the user's real position. The returned address should therefore be treated as a nearby address match, not as a real-time navigation position.

This implementation does not require a Google API key and does not call Google Geocoding or Google Maps.
