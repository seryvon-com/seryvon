# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Couche de persistance : base déclarative et fabrique de sessions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from seryvon.core.config import get_settings


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles ORM."""


def get_engine() -> Engine:
    """Crée l'engine SQLAlchemy depuis la config."""
    return create_engine(get_settings().database_url, future=True)


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session transactionnelle : commit si succès, rollback sinon, fermeture garantie."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
