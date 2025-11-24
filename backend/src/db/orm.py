import os
from pathlib import Path
import logging
from contextlib import contextmanager
from typing import Any, Generator
from psycopg import Cursor

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql://app:app@localhost:5432/app"  # HACK: debugger
)
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")


@contextmanager
def db_cursor() -> Generator[Cursor, None, None]:
    conn = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=1,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def select_one(query: str, *params: Any) -> dict[str, Any] | None:
    with db_cursor() as cur:
        cur.execute(query, params or None)
        return cur.fetchone()


def select_all(query: str, *params: Any) -> list[dict[str, Any]]:
    with db_cursor() as cur:
        cur.execute(query, params or None)
        return cur.fetchall()


def insert(query: str, *params: Any) -> dict[str, Any] | None:
    with db_cursor() as cur:
        cur.execute(query, params or None)
        if cur.description:
            return cur.fetchone()
        return None


def delete(query: str, *params: Any) -> dict[str, Any] | None:
    with db_cursor() as cur:
        cur.execute(query, params or None)
        return cur.statusmessage == "DELETE 1"


def init_db() -> None:
    path = Path(__file__).parent / "db_schema.sql"
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    ddl = path.read_text()
    statements = [s.strip() for s in ddl.split(";") if s.strip()]

    try:
        with db_cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        log.info("DB initialized")
    except Exception as e:
        log.error("Failed to initialize DB: %s", e)
        raise
