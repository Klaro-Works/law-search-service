"""
Configuration settings for Law Search Service
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Service
    service_name: str = "law-search-service"
    service_version: str = "1.0.0"
    log_level: str = "INFO"

    # OpenAI
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (required only when embedding/LLM features are enabled)",
    )
    openai_embedding_model: str = "text-embedding-3-small"

    # Law.go.kr API
    law_api_key: str = Field(
        default="",
        description="law.go.kr OC API key (required for calling law.go.kr DRF endpoints)",
    )
    law_api_base_url: str = "https://www.law.go.kr"

    # Qdrant
    qdrant_url: str = Field(
        default="",
        description="Qdrant endpoint URL (required only when vector search is enabled)",
    )
    qdrant_api_key: str = ""
    qdrant_collection_laws: str = "laws"
    qdrant_collection_articles: str = "articles"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "law_search"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_url_sync(self) -> str:
        """PostgreSQL connection URL for synchronous operations"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        """Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "law-documents"
    minio_secure: bool = False

    # Collection Schedule
    default_collection_schedule: str = "0 2 * * *"  # Daily at 2 AM

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # Search
    default_top_k: int = 20
    max_top_k: int = 100
    cache_ttl: int = 3600  # 1 hour

    # Vector Store Configuration
    vector_store_type: str = "file_system"  # qdrant, in_memory, file_system
    vector_store_fs_path: str = "./vector_data"
    vector_embedding_dimension: int = 1536  # OpenAI text-embedding-3-small

    # Cache Configuration
    cache_type: str = "in_memory"  # redis, in_memory


# Global settings instance
settings = Settings()
