from collections.abc import Sequence
from typing import Any, Protocol

from app.core.config import (
    RDS_DATABASE,
    RDS_HOST,
    RDS_PASSWORD,
    RDS_PORT,
    RDS_USER,
)


class DatabaseClient(Protocol):
    def fetch_all(self, query: str, params: Sequence[object] = ()) -> list[dict[str, Any]]:
        ...


class MySQLClient:
    def fetch_all(self, query: str, params: Sequence[object] = ()) -> list[dict[str, Any]]:
        import mysql.connector

        connection = mysql.connector.connect(
            host=RDS_HOST,
            port=RDS_PORT,
            database=RDS_DATABASE,
            user=RDS_USER,
            password=RDS_PASSWORD,
        )
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()
