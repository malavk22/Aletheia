from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    # Set to true in production so the session cookie is only sent over HTTPS.
    cookie_secure: bool = False
    # Where uploaded files are stored (relative to the backend folder).
    upload_dir: str = "uploads"
    max_upload_mb: int = 20
    # Full path to tesseract.exe, only needed if it is somewhere unusual. When
    # empty, it is looked for on the PATH and in its default Windows folder.
    tesseract_cmd: str | None = None
    # Where the embedding model is downloaded to on first use (about 67 MB).
    embedding_cache_dir: str = "models"
    # Writes the answers (V0.4). The free key from aistudio.google.com works;
    # without a key everything else runs, only questions can't be answered.
    gemini_api_key: str | None = None
    llm_model: str = "gemini-3.8-flash"
    # Tried once when the main model is busy or over its free limit.
    llm_fallback_model: str | None = "gemini-2.5-flash"


settings = Settings()
