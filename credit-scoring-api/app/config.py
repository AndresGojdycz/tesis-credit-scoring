from pathlib import Path
from typing import List
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class Settings:
    """Configuración de la aplicación"""
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    ARTIFACTS_DIR: Path = BASE_DIR / "artifacts"
    
    # Modelo
    MODEL_PATH: Path = ARTIFACTS_DIR / "model.pkl"
    FEATURE_NAMES_PATH: Path = ARTIFACTS_DIR / "feature_names.pkl"

    # API
    API_TITLE: str = "Credit Scoring API"
    API_VERSION: str = "3.0.0"
    API_DESCRIPTION: str = """
    API REST para predicción de default crediticio empresarial.

    **Características:**
    - Predicción de créditos vencidos en los 12 meses siguientes al cierre del balance
    - Modelo y métricas vigentes en GET /model/info (model_card.json)
    - Métricas y scorecard vigentes en GET /model/info (model_card.json)
    - Explainability con LIME
    - Validación automática de inputs
    """
    
    # Scoring parameters
    PDO: int = 50
    BASE_SCORE: int = 600
    
    # Limits
    MAX_BATCH_SIZE: int = 100
    REQUEST_TIMEOUT: int = 30
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Environment
    ENV: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENV == "development"
    
settings = Settings()
