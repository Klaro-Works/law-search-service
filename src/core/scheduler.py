"""Scheduler for automated law collection

APScheduler를 사용한 주기적 법령 데이터 수집 스케줄러입니다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel

from src.config.settings import settings
from src.pipeline.collectors.law_collector import fetch_law_detail, search_law
from src.repository.db import get_db_session
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScheduleConfig(BaseModel):
    """스케줄러 설정"""

    collection_schedule: str = "0 2 * * *"  # 매일 새벽 2시
    enable_auto_collection: bool = False
    top_k_per_batch: int = 100


class LawScheduler:
    """법령 수집 스케줄러"""

    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self._initialized = False

    async def initialize(self) -> None:
        """스케줄러 초기화"""
        if self.config.enable_auto_collection:
            self.scheduler.add_job(
                self._collect_laws,
                trigger=CronTrigger.from_crontab(self.config.collection_schedule),
                id="collect_laws",
                name="Collect Laws from law.go.kr",
                replace_existing=True,
            )
            logger.info(f"✅ Scheduled law collection: {self.config.collection_schedule}")
        else:
            logger.info("Auto collection is disabled")

        self._initialized = True
        self.scheduler.start()

    async def shutdown(self) -> None:
        """스케줄러 종료"""
        if self._initialized:
            self.scheduler.shutdown()
            self._initialized = False
            logger.info("Scheduler shutdown complete")

    async def _collect_laws(self) -> None:
        """법령 수집 작업"""
        logger.info("=" * 50)
        logger.info("Starting law collection...")
        start_time = datetime.now()

        try:
            async for db in get_db_session():
                top_queries = [
                    "개인정보 보호",
                    "저작권",
                    "민법",
                    "형법",
                    "노동",
                    "회사",
                    "세금",
                    "의료",
                    "교육",
                ]

                collected_count = 0
                for query in top_queries:
                    try:
                        laws = await search_law(
                            query=query,
                            top_k=self.config.top_k_per_batch // len(top_queries),
                        )

                        for law_data in laws:
                            law_id = law_data.get("법령ID")
                            if law_id:
                                detail = await fetch_law_detail(
                                    law_id=law_id,
                                    include_articles=True,
                                    include_full_text=False,
                                )

                                if detail:
                                    from src.main import _cache_law_detail_to_db

                                    await _cache_law_detail_to_db(db, detail)
                                    collected_count += 1
                                    logger.info(f"  Collected: {detail.get('law_name_kr')}")

                        await db.commit()

                    except Exception as e:
                        logger.error(f"Failed to collect laws for query '{query}': {e}")
                        continue

                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info("=" * 50)
                logger.info(f"Law collection completed: {collected_count} laws in {elapsed:.1f}s")
                logger.info("=" * 50)

        except Exception as e:
            logger.exception(f"Law collection failed: {e}")

    async def trigger_collection(self) -> dict[str, Any]:
        """수동으로 수집 트리거

        Returns:
            수집 결과 통계
        """
        logger.info("Manually triggering law collection...")
        start_time = datetime.now()

        await self._collect_laws()

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "triggered_at": start_time.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "duration_seconds": elapsed,
            "status": "completed",
        }

    def get_jobs(self) -> list[dict[str, Any]]:
        """등록된 작업 목록 반환"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                }
            )
        return jobs


# Global scheduler instance
_scheduler: LawScheduler | None = None


async def get_scheduler() -> LawScheduler:
    """전역 스케줄러 인스턴스 반환

    Returns:
        LawScheduler 인스턴스
    """
    global _scheduler

    if _scheduler is None:
        config = ScheduleConfig(
            collection_schedule=settings.default_collection_schedule,
            enable_auto_collection=False,  # 기본은 비활성화
        )
        _scheduler = LawScheduler(config)
        await _scheduler.initialize()

    return _scheduler


async def shutdown_scheduler() -> None:
    """스케줄러 종료"""
    global _scheduler

    if _scheduler:
        await _scheduler.shutdown()
        _scheduler = None
