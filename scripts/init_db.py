"""Initialize PostgreSQL schema for law-search-service.

This creates the minimal tables required to persist laws/articles.

Usage:
  python3 scripts/init_db.py

Prereqs:
  - PostgreSQL is running. (This script will try to create the target DB if missing.)
  - .env contains POSTGRES_* values (see README).
"""

from __future__ import annotations

import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine

from src.config.settings import settings
from src.models.entities import Base


def _ensure_database_exists() -> None:
    """
    Create the target database if it doesn't exist.
    Requires that the configured user has CREATE DATABASE privileges.
    """
    try:
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname="postgres",
        )
    except Exception as e:
        print(f"❌ Failed to connect to postgres DB for bootstrap: {e}", file=sys.stderr)
        return

    try:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.postgres_db,))
            exists = cur.fetchone() is not None
            if exists:
                print(f"✅ Database exists: {settings.postgres_db}")
                return

            cur.execute(f'CREATE DATABASE "{settings.postgres_db}"')
            print(f"✅ Database created: {settings.postgres_db}")
    except Exception as e:
        print(
            "⚠️  Could not create database automatically. "
            f"Please create DB '{settings.postgres_db}' manually. ({e})",
            file=sys.stderr,
        )
    finally:
        conn.close()


def main() -> None:
    _ensure_database_exists()
    engine = create_engine(settings.postgres_url_sync)
    Base.metadata.create_all(engine)
    print("✅ DB schema initialized (tables created if missing)")


if __name__ == "__main__":
    main()
