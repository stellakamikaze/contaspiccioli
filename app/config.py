"""Configuration settings for Contaspiccioli."""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    secret_key: str = "change-me-in-production"
    debug: bool = False
    database_url: str = "sqlite:///data/contaspiccioli.db"

    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Paths
    base_dir: Path = Path(__file__).parent.parent

    # Budget defaults
    default_income: float = 3500.0

    # Tax settings (P.IVA Forfettaria)
    inps_rate: float = 0.2598
    coefficient: float = 0.78
    tax_rate: float = 0.05

    # Budget percentages
    fixed_percentage: float = 0.3337
    variable_percentage: float = 0.2546
    tax_percentage: float = 0.3143
    investment_percentage: float = 0.0974

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
