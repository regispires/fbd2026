from pydantic import SecretStr, computed_field
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


settings = Settings()  # pyright: ignore[reportCallIssue]
