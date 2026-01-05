"""SQLAlchemy ORM entities.

Minimal schema for persisting law metadata + articles.
Designed so we can later add:
- PostgreSQL FTS columns/indexes
- Qdrant vector ids
- Incremental update fields
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Law(Base):
    __tablename__ = "laws"

    law_id: Mapped[str] = mapped_column(String(32), primary_key=True)

    law_serial: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    law_name_kr: Mapped[str] = mapped_column(String(512), nullable=False)
    law_abbr: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    department: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    law_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    enforce_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    promulgate_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    detail_link: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    articles: Mapped[list[LawArticle]] = relationship(
        back_populates="law",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LawArticle(Base):
    __tablename__ = "law_articles"
    __table_args__ = (
        UniqueConstraint("law_id", "article_no", name="uq_law_articles_law_id_article_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    law_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("laws.law_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    article_no: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    vector_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    law: Mapped[Law] = relationship(back_populates="articles")
