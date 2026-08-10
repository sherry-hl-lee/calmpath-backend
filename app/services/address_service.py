from __future__ import annotations

from app.core.database import DatabaseClient, MySQLClient
from app.schemas.refuge import RefugeAddress


ADDRESS_QUERY = """
SELECT address, address_latitude, address_longitude, address_distance_m, address_source
FROM backend_refuge_candidates
WHERE latitude = %s
  AND longitude = %s
  AND address_match_status = 'MATCHED'
LIMIT 1
"""


class AddressService:
    def __init__(self, database_client: DatabaseClient | None = None) -> None:
        self._database_client = database_client or MySQLClient()

    def find_address(self, latitude: float, longitude: float) -> RefugeAddress | None:
        rows = self._database_client.fetch_all(ADDRESS_QUERY, (latitude, longitude))
        if not rows:
            return None

        row = rows[0]
        address = row.get("address")
        if not isinstance(address, str) or not address.strip():
            return None

        return RefugeAddress(
            address=address.strip(),
            latitude=float(row["address_latitude"]),
            longitude=float(row["address_longitude"]),
            match_distance_m=float(row["address_distance_m"]),
            source=str(row["address_source"]),
        )
