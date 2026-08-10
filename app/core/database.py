from collections.abc import Sequence
from typing import Any, Protocol

from app.core.config import (
    RDS_DATABASE,
    RDS_HOST,
    RDS_PASSWORD,
    RDS_PORT,
    RDS_SSL_CA,
    RDS_USER,
)


class DatabaseClient(Protocol):
    def fetch_all(self, query: str, params: Sequence[object] = ()) -> list[dict[str, Any]]:
        ...


class MySQLClient:
    def fetch_all(self, query: str, params: Sequence[object] = ()) -> list[dict[str, Any]]:
        import mysql.connector

        connection_options: dict[str, object] = dict(
            host=RDS_HOST,
            port=RDS_PORT,
            database=RDS_DATABASE,
            user=RDS_USER,
            password=RDS_PASSWORD,
        )
        if RDS_SSL_CA:
            connection_options.update(
                ssl_ca=RDS_SSL_CA,
                ssl_verify_cert=True,
                ssl_verify_identity=True,
            )

        connection = mysql.connector.connect(**connection_options)
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute(query, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()
