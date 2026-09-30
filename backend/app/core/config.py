from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    # Set to true in production so the session cookie is only sent over HTTPS.
    cookie_secure: bool = False
    # Where uploaded files are stored (relative to the backend folder).
    upload_dir: str = "uploads"
    max_upload_mb: int = 20


settings = Settings()
