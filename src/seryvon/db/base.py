# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Persistence layer: declarative base and session factory."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from seryvon.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _register_jsonb_dumpers(dbapi_conn: Any, conn_rec: Any) -> None:
    """Register dict → JSONB dumper for psycopg3.

    psycopg3 has no built-in dict→JSONB adapter; without this, any JSONB
    column receiving a plain Python dict raises ProgrammingError.
    Lists are intentionally excluded: they map to ARRAY(Text) columns.
    """
    from psycopg.types.json import JsonbDumper

    dbapi_conn.adapters.register_dumper(dict, JsonbDumper)


def get_engine() -> Engine:
    """Create the SQLAlchemy engine from the config."""
    engine = create_engine(
        get_settings().database_url,
        future=True,
        json_serializer=json.dumps,
        json_deserializer=json.loads,
    )
    event.listen(engine, "connect", _register_jsonb_dumpers)
    return engine


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, rollback otherwise, guaranteed close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
