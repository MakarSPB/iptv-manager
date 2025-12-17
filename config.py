from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_host: str = Field("127.0.0.1", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    playlists_dir: str = Field("storage/playlists", env="PLAYLISTS_DIR")
    debug: bool = Field(False, env="DEBUG")

    class Config:
        env_file = ".env"


settings = Settings()