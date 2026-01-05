"""
Logging utilities
"""
import logging
import sys
from typing import Optional

from src.config.settings import settings


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name or "law-search-service")
    
    # 이미 핸들러가 설정되어 있으면 스킵
    if logger.handlers:
        return logger
    
    # 로그 레벨 설정
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 콘솔 핸들러
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # 포맷터
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger
