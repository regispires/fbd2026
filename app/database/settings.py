from datetime import timedelta
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic.networks import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URI: SecretStr
    # TIMESTAMPTZ chegam no horário local e as páginas os exibem sem converter
    DATABASE_TIMEZONE: str = "America/Fortaleza"

    ENVIRONMENT: Literal["DEVELOPMENT", "PRODUCTION"]
    SESSION_DURATION_HOURS: timedelta = timedelta(hours=24)

    # utilizado para parâmetros de sessão (diferente do cookie de autenticação)
    STORAGE_SECRET: SecretStr

    @field_validator("DATABASE_URI")
    @classmethod
    def _validate_database_uri(cls, value: SecretStr) -> SecretStr:
        """Falha na inicialização se a URI não for de um banco PostgreSQL"""
        _ = PostgresDsn(value.get_secret_value())
        return value

    @field_validator("SESSION_DURATION_HOURS", mode="before")
    @classmethod
    def _converter_duration(cls, value: object) -> object:
        """Transforma a duração da sessão em um timedelta"""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return timedelta(hours=value)
        if isinstance(value, str):
            return timedelta(hours=float(value))
        return value


settings = Settings()  # pyright: ignore[reportCallIssue]
