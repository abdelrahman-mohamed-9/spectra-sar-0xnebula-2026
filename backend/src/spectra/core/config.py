from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SPECTRA-SAR Backend"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    internal_api_key: str | None = None
    jwt_secret: str | None = None
    jwt_issuer: str = "spectra-sar"
    jwt_audience: str = "spectra-sar-api"
    jwt_ttl_minutes: int = Field(default=15, ge=1, le=60)
    database_url: str | None = None
    redis_url: str | None = None
    s3_endpoint_url: str | None = None
    s3_bucket: str = "spectra-sar"
    s3_region: str = "us-east-1"
    max_upload_bytes: int = Field(default=536870912,ge=1,le=5368709120)
    s3_access_key: str | None = None
    s3_secret_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
