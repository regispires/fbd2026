from datetime import timedelta
from typing import Literal

from pydantic import SecretStr, computed_field, field_validator
from pydantic.networks import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @computed_field
    @property
    def DATABASE_URI(self) -> SecretStr:
        return SecretStr(
            PostgresDsn.build(
                scheme="postgresql+psycopg2",  # driver configurado para conexão com o banco
                path=self.DATABASE_NAME.get_secret_value(),
                username=self.DATABASE_USER.get_secret_value(),
                password=self.DATABASE_PASSWORD.get_secret_value(),
                host=self.DATABASE_HOST,
                port=self.DATABASE_PORT,
            ).encoded_string()
        )

    DATABASE_USER: SecretStr
    DATABASE_PASSWORD: SecretStr
    DATABASE_NAME: SecretStr
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    # TIMESTAMPTZ chegam no horário local e as páginas os exibem sem converter
    DATABASE_TIMEZONE: str = "America/Fortaleza"

    ENVIRONMENT: Literal["DEVELOPMENT", "PRODUCTION"]
    SESSION_DURATION_HOURS: timedelta = timedelta(hours=24)

    # utilizado para parâmetros de sessão (diferente do cookie de autenticação)
    STORAGE_SECRET: SecretStr

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
