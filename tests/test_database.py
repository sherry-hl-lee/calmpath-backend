from app.core import database


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple]] = []
        self.closed = False

    def execute(self, query: str, params=()) -> None:
        self.executions.append((query, params))

    def fetchall(self) -> list[dict]:
        return [{"status": "ok"}]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self, dictionary: bool = False) -> FakeCursor:
        assert dictionary is True
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


def test_mysql_client_sets_utc_and_verifies_rds_identity(monkeypatch) -> None:
    import mysql.connector

    connection = FakeConnection()
    options: dict[str, object] = {}

    def connect(**kwargs):
        options.update(kwargs)
        return connection

    monkeypatch.setattr(mysql.connector, "connect", connect)
    monkeypatch.setattr(database, "RDS_SSL_CA", "/test/rds-ca.pem")

    rows = database.MySQLClient().fetch_all("SELECT %s AS value", (1,))

    assert rows == [{"status": "ok"}]
    assert connection.cursor_instance.executions == [
        ("SET time_zone = '+00:00'", ()),
        ("SELECT %s AS value", (1,)),
    ]
    assert options["ssl_ca"] == "/test/rds-ca.pem"
    assert options["ssl_verify_cert"] is True
    assert options["ssl_verify_identity"] is True
    assert connection.cursor_instance.closed is True
    assert connection.closed is True
