from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    syzygy_path: str = "syzygy"


settings = Settings()
