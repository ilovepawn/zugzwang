from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    syzygy_path: str = "syzygy"

    model_config = {"env_file": ".env"}


settings = Settings()
