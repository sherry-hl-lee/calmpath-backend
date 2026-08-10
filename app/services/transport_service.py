import csv
import io
import time
import zipfile
from dataclasses import dataclass

import httpx

from app.core.config import GTFS_URL, TRANSIT_RADIUS_M
from app.schemas.route import TransitAccessPoint
from app.services.route_geometry import Coordinate, distance_to_route_m


@dataclass(frozen=True)
class TransportStop:
    id: str
    name: str
    type: str
    coordinate: Coordinate


class TransportService:
    CACHE_SECONDS = 24 * 60 * 60

    def __init__(self) -> None:
        self._stops: list[TransportStop] | None = None
        self._loaded_at = 0.0

    @staticmethod
    def _read_branch_stops(
        outer_archive: zipfile.ZipFile,
        branch: str,
        stop_type: str,
    ) -> list[TransportStop]:
        nested_member = next(
            (
                member
                for member in outer_archive.namelist()
                if member.replace("\\", "/").strip("/").lower()
                == f"{branch}/google_transit.zip"
            ),
            None,
        )
        if nested_member is None:
            return []

        with outer_archive.open(nested_member) as nested_raw:
            nested_bytes = nested_raw.read()
        with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested_archive:
            stops_member = next(
                (
                    member
                    for member in nested_archive.namelist()
                    if member.replace("\\", "/")
                    .strip("/")
                    .lower()
                    .endswith("stops.txt")
                ),
                None,
            )
            if stops_member is None:
                return []

            with nested_archive.open(stops_member) as raw_file:
                rows = list(
                    csv.DictReader(io.TextIOWrapper(raw_file, encoding="utf-8-sig"))
                )

        # Metro train branch 2 includes platform and station records. US1.1
        # asks for train stations, so prefer parent station records when they
        # are present. Tram branch 3 uses ordinary stop/platform records.
        if stop_type == "train":
            station_rows = [row for row in rows if row.get("location_type") == "1"]
            if station_rows:
                rows = station_rows
        else:
            rows = [row for row in rows if row.get("location_type", "") in {"", "0"}]

        stops: list[TransportStop] = []
        for row in rows:
            try:
                coordinate = Coordinate(
                    latitude=float(row["stop_lat"]),
                    longitude=float(row["stop_lon"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            stops.append(
                TransportStop(
                    id=str(row.get("stop_id", "")),
                    name=str(row.get("stop_name", "Unnamed stop")),
                    type=stop_type,
                    coordinate=coordinate,
                )
            )
        return stops

    async def _load_stops(self, client: httpx.AsyncClient) -> list[TransportStop]:
        if (
            self._stops is not None
            and time.monotonic() - self._loaded_at < self.CACHE_SECONDS
        ):
            return self._stops

        response = await client.get(GTFS_URL)
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        stops: list[TransportStop] = []

        stops.extend(self._read_branch_stops(archive, "2", "train"))
        stops.extend(self._read_branch_stops(archive, "3", "tram"))

        self._stops = list({(stop.type, stop.id): stop for stop in stops}.values())
        self._loaded_at = time.monotonic()
        return self._stops

    async def nearby(
        self,
        client: httpx.AsyncClient,
        route_samples: list[Coordinate],
    ) -> list[TransitAccessPoint]:
        access_points: list[TransitAccessPoint] = []
        for stop in await self._load_stops(client):
            distance_m = distance_to_route_m(stop.coordinate, route_samples)
            if distance_m <= TRANSIT_RADIUS_M:
                access_points.append(
                    TransitAccessPoint(
                        id=stop.id,
                        name=stop.name,
                        type=stop.type,
                        latitude=stop.coordinate.latitude,
                        longitude=stop.coordinate.longitude,
                        distance_to_route_m=round(distance_m, 1),
                    )
                )

        access_points.sort(key=lambda stop: stop.distance_to_route_m)
        return access_points[:20]
