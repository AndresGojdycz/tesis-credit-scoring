from fastapi import FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import json
import logging
import time

from app.config import settings
from app.models import (
    PredictionRequest, BatchPredictionRequest,
    PredictionResponse, HealthResponse
)
from app.predictor import predictor
from app.explainer import lime_explainer
from app import form_bce
from app.macro import _cargar as cargar_macro

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Startup time
startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    logger.info("🚀 Iniciando Credit Scoring API...")
    
    try:
        # Cargar modelo
        predictor.load_model()
        
        # Inicializar LIME (opcional)
        try:
            lime_explainer.initialize()
        except Exception as e:
            logger.warning(f"LIME no inicializado: {e}")
        
        logger.info("✅ API lista para recibir requests")
        
    except Exception as e:
        logger.error(f"❌ Error en startup: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Cerrando Credit Scoring API...")


# FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["Status"])
async def root():
    """Root endpoint"""
    return {
        "message": "Credit Scoring API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Status"])
async def health_check():
    """Health check endpoint"""
    uptime = time.time() - startup_time
    
    return HealthResponse(
        status="healthy" if predictor.model_loaded else "unhealthy",
        model_loaded=predictor.model_loaded,
        model_version=settings.API_VERSION,
        uptime_seconds=uptime
    )


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict_default(request: PredictionRequest):
    """
    Predice probabilidad de default para una empresa.
    
    **Input:** Features financieros de la empresa
    
    **Output:**
    - Probabilidad de default (0-1)
    - Credit score (0-1500, PDO=50, base 600)
    - Banda de riesgo (Bueno / Aceptable / Comprometido / Critico)
    - Explicación LIME (opcional)
    """
    try:
        # Predicción
        prediction = predictor.predict(request.features)
        
        # Explicación (si se solicita)
        explanation = None
        if request.explain:
            try:
                features_dict = request.features.dict(by_alias=True)
                explanation = lime_explainer.explain_prediction(
                    features_dict,
                    probability=prediction["probability"],
                    score=prediction["score"],
                    risk_rating=prediction["risk_rating"].category,
                )
            except Exception as e:
                logger.warning(f"No se pudo generar explicación: {e}")
        
        # Response
        return PredictionResponse(
            company_id=request.company_id,
            probability=prediction["probability"],
            score=prediction["score"],
            risk_rating=prediction["risk_rating"],
            explanation=explanation,
            warnings=prediction.get("warnings"),
            model_version=settings.API_VERSION
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error en /predict: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@app.post("/predict/batch", tags=["Prediction"])
async def predict_batch(request: BatchPredictionRequest):
    """
    Predicción batch para múltiples empresas.
    
    **Límite:** 100 empresas por request
    """
    try:
        predictions = predictor.predict_batch(request.companies)
        
        responses = []
        for i, pred in enumerate(predictions):
            if pred.get("error"):
                responses.append({
                    "index": i,
                    "error": pred["error"]
                })
            else:
                responses.append({
                    "index": i,
                    "probability": pred["probability"],
                    "score": pred["score"],
                    "risk_rating": pred["risk_rating"],
                    "warnings": pred.get("warnings"),
                })
        
        return {
            "total": len(request.companies),
            "successful": sum(1 for r in responses if "error" not in r),
            "failed": sum(1 for r in responses if "error" in r),
            "results": responses
        }
        
    except Exception as e:
        logger.error(f"Error en /predict/batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


MAX_FORMULARIO_BYTES = 10 * 1024 * 1024


@app.post("/importar/form-bce", tags=["Importación"])
async def importar_form_bce(request: Request):
    """
    Lee el formulario de estados contables del BROU (FORM_BCE, versión 08/08/2018) y devuelve los campos
    del formulario del dashboard.

    **Input:** el .xlsx completado por el cliente, como cuerpo de la request (application/octet-stream).

    **Output:**
    - `campos`: mismos nombres que las columnas del CSV de carga (partidas, año anterior con el sufijo
      " (anterior)", FECHA_CIERRE y cualitativas)
    - `avisos`: lo que conviene revisar antes de evaluar (actividad propuesta, cuadres)
    """
    contenido = await request.body()
    if not contenido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No llegó ningún archivo.")
    if len(contenido) > MAX_FORMULARIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="El archivo supera los 10 MB.")
    macro = cargar_macro() or {}
    try:
        return await run_in_threadpool(form_bce.importar, contenido, macro.get("actividad_a_sector"))
    except form_bce.FormularioInvalido as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Error en /importar/form-bce: {type(e).__name__}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No se pudo leer el formulario. Verificá que sea el FORM_BCE versión 2018.")


@app.get("/model/info", tags=["Model"])
async def model_info():
    """Información del modelo (fuente unica de verdad: artifacts/model_card.json)."""
    if not predictor.model_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo no cargado"
        )

    model_card_path = settings.ARTIFACTS_DIR / "model_card.json"
    if not model_card_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"model_card.json no encontrado en {model_card_path}. "
                "Correr `python export_artifacts_for_api.py` para regenerar."
            ),
        )

    with open(model_card_path) as f:
        model_card = json.load(f)

    # Datos derivados del modelo cargado en runtime
    return {
        **model_card,
        "num_features": len(predictor.feature_names),
        "features_preview": predictor.feature_names[:10],
    }


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)}
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
