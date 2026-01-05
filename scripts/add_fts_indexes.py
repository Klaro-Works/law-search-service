"""Add PostgreSQL FTS indexes for law search

Full-Text Search를 위한 GIN 인덱스 및 트리거를 추가합니다.

Usage:
  python3 scripts/add_fts_indexes.py

This script:
1. Add tsvector columns to laws/law_articles tables
2. Create GIN indexes
3. Create triggers for auto-update tsvector columns
"""

from __future__ import annotations

import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def execute_sql(conn: psycopg2.extensions.connection, sql: str) -> None:
    """SQL 실행"""
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
        logger.info(f"✅ Executed SQL successfully")
    except Exception as e:
        logger.error(f"❌ Failed to execute SQL: {e}")
        raise


def add_law_fts_columns(conn: psycopg2.extensions.connection) -> None:
    """laws 테이블에 FTS 컬럼 추가"""

    sql = """
    -- tsvector 컬럼 추가
    ALTER TABLE laws ADD COLUMN IF NOT EXISTS tsv tsvector;

    -- tsv 컬럼 업데이트 (한글 + 영어 형태소 분석)
    UPDATE laws
    SET tsv = to_tsvector('korean',
        COALESCE(law_name_kr, '') || ' ' ||
        COALESCE(law_abbr, '') || ' ' ||
        COALESCE(department, '') || ' ' ||
        COALESCE(law_type, '') || ' ' ||
        COALESCE(status, '')
    )
    WHERE tsv IS NULL;

    -- GIN 인덱스 생성
    CREATE INDEX IF NOT EXISTS idx_laws_tsv ON laws USING GIN(tsv);

    -- 자동 업데이트 트리거 함수
    CREATE OR REPLACE FUNCTION laws_tsv_trigger() RETURNS trigger AS $$
    BEGIN
        NEW.tsv := to_tsvector('korean',
            COALESCE(NEW.law_name_kr, '') || ' ' ||
            COALESCE(NEW.law_abbr, '') || ' ' ||
            COALESCE(NEW.department, '') || ' ' ||
            COALESCE(NEW.law_type, '') || ' ' ||
            COALESCE(NEW.status, '')
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- 트리거 등록
    DROP TRIGGER IF EXISTS laws_tsv_update_trigger ON laws;
    CREATE TRIGGER laws_tsv_update_trigger
    BEFORE INSERT OR UPDATE ON laws
    FOR EACH ROW
    EXECUTE FUNCTION laws_tsv_trigger();
    """

    execute_sql(conn, sql)
    logger.info("✅ Added FTS columns/indexes/triggers to 'laws' table")


def add_article_fts_columns(conn: psycopg2.extensions.connection) -> None:
    """law_articles 테이블에 FTS 컬럼 추가"""

    sql = """
    -- tsvector 컬럼 추가
    ALTER TABLE law_articles ADD COLUMN IF NOT EXISTS tsv tsvector;

    -- tsv 컬럼 업데이트
    UPDATE law_articles
    SET tsv = to_tsvector('korean',
        COALESCE(article_no, '') || ' ' ||
        COALESCE(title, '') || ' ' ||
        COALESCE(content, '')
    )
    WHERE tsv IS NULL;

    -- GIN 인덱스 생성
    CREATE INDEX IF NOT EXISTS idx_law_articles_tsv ON law_articles USING GIN(tsv);

    -- 자동 업데이트 트리거 함수
    CREATE OR REPLACE FUNCTION law_articles_tsv_trigger() RETURNS trigger AS $$
    BEGIN
        NEW.tsv := to_tsvector('korean',
            COALESCE(NEW.article_no, '') || ' ' ||
            COALESCE(NEW.title, '') || ' ' ||
            COALESCE(NEW.content, '')
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- 트리거 등록
    DROP TRIGGER IF EXISTS law_articles_tsv_update_trigger ON law_articles;
    CREATE TRIGGER law_articles_tsv_update_trigger
    BEFORE INSERT OR UPDATE ON law_articles
    FOR EACH ROW
    EXECUTE FUNCTION law_articles_tsv_trigger();
    """

    execute_sql(conn, sql)
    logger.info("✅ Added FTS columns/indexes/triggers to 'law_articles' table")


def main() -> None:
    """메인 함수"""
    try:
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname=settings.postgres_db,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        logger.info(f"Connected to PostgreSQL: {settings.postgres_db}")

        add_law_fts_columns(conn)
        add_article_fts_columns(conn)

        logger.info("✅ All FTS indexes added successfully")
        conn.close()

    except Exception as e:
        logger.exception("Failed to add FTS indexes")
        sys.exit(1)


if __name__ == "__main__":
    main()
