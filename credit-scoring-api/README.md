# 🏦 Credit Scoring API

API REST para predicción de default crediticio empresarial usando Machine Learning.

## 📊 Características

- ✅ **Predicción temporal**: Default 6-12 meses adelante
- ✅ **Random Forest**: AUC 0.9103 (Elite tier)
- ✅ **Explainability**: LIME integrado
- ✅ **Validación automática**: Pydantic schemas
- ✅ **Production-ready**: Logging, health checks, error handling
- ✅ **Documentación interactiva**: Swagger UI auto-generada

## 🚀 Quick Start

### 1. Preparar Artifacts (Primera vez)

Desde el directorio raíz de tesis:

```bash
# Exportar modelo y feature names desde el notebook
python export_artifacts_for_api.py
```

Esto copiará:
- ✅ `rf_model_calibrated_raw_future.pkl` → `credit-scoring-api/artifacts/`
- ✅ `feature_names.pkl` → `credit-scoring-api/artifacts/`
- ✅ `model_metadata.csv` → `credit-scoring-api/artifacts/`

### 2. Instalar Dependencias

```bash
cd credit-scoring-api
pip install -r requirements.txt
```

### 3. Ejecutar API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en: **http://localhost:8000**

### 4. Acceder Documentación

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 5. Probar API

En otra terminal:

```bash
python test_api_simple.py
```

---

## 📡 Endpoints

### `GET /` - Root
```bash
curl http://localhost:8000/
```

### `GET /health` - Health Check
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_version": "1.0.0",
  "uptime_seconds": 123.45
}
```

### `GET /model/info` - Model Info
```bash
curl http://localhost:8000/model/info
```

**Response:**
```json
{
  "model_type": "Random Forest (Calibrated)",
  "num_features": 82,
  "target": "DEFAULT_FUTURE (6-12 months)",
  "performance": {
    "test_auc": 0.9103,
    "test_ks": 0.7105
  }
}
```

### `POST /predict` - Predicción Individual

**Request:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "12345678-9",
    "features": {
      "TOTAL ACTIVO": 5000000,
      "TOTAL PASIVO": 3000000,
      "TOTAL PATRIMONIO": 2000000,
      "ROA": 0.15,
      "ROE": 0.22,
      "Capital": 500000
    },
    "explain": false
  }'
```

**Response:**
```json
{
  "company_id": "12345678-9",
  "probability": 0.05,
  "score": 750,
  "risk_rating": {
    "category": "AAA",
    "description": "Muy bajo riesgo de default",
    "color": "green"
  },
  "prediction_timestamp": "2024-01-15T10:30:00Z",
  "model_version": "1.0.0"
}
```

### `POST /predict` - Con Explicación LIME

**Request:**
```json
{
  "company_id": "98765432-1",
  "features": {
    "TOTAL ACTIVO": 1000000,
    "TOTAL PASIVO": 850000,
    "ROA": -0.05,
    "Relacion_deuda_patrimonio": 4.5
  },
  "explain": true
}
```

**Response:**
```json
{
  "company_id": "98765432-1",
  "probability": 0.75,
  "score": 320,
  "risk_rating": {
    "category": "D",
    "description": "Muy alto riesgo de default",
    "color": "red"
  },
  "explanation": {
    "top_features": [
      {"feature": "ROA <= -0.02", "contribution": 0.234},
      {"feature": "Relacion_deuda_patrimonio > 3.0", "contribution": 0.187},
      {"feature": "Capital <= 100000", "contribution": 0.156}
    ],
    "prediction": 0.76,
    "intercept": 0.08
  }
}
```

### `POST /predict/batch` - Predicción Batch

**Request:**
```json
{
  "companies": [
    {"TOTAL ACTIVO": 5000000, "ROA": 0.15},
    {"TOTAL ACTIVO": 1000000, "ROA": -0.05},
    {"TOTAL ACTIVO": 3000000, "ROA": 0.08}
  ],
  "explain": false
}
```

**Response:**
```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "probability": 0.05,
      "score": 750,
      "risk_rating": {"category": "AAA", ...}
    },
    {
      "index": 1,
      "probability": 0.72,
      "score": 340,
      "risk_rating": {"category": "D", ...}
    },
    {
      "index": 2,
      "probability": 0.12,
      "score": 680,
      "risk_rating": {"category": "A", ...}
    }
  ]
}
```

### `POST /importar/form-bce` - Importar el formulario del BROU

Lee el formulario de estados contables del BROU (FORM_BCE, versión 08/08/2018) completado por el cliente y devuelve
los campos del formulario del dashboard. El cuerpo es el .xlsx tal cual.

```bash
curl -X POST http://localhost:8000/importar/form-bce \
  -H "Content-Type: application/octet-stream" \
  --data-binary @ejemplos/formulario_bce/empresa_bueno.xlsx
```

**Response:**
- `campos`: mismos nombres que las columnas del CSV de carga del dashboard (partidas del modelo, año anterior con el
  sufijo " (anterior)", `FECHA_CIERRE` y cualitativas). La actividad se propone a partir del giro declarado.
- `avisos`: lo que conviene revisar antes de evaluar (actividad propuesta, cuadres).

El formulario no trae el importe (`IMPORTE_MN`): se completa a mano en el dashboard. La correspondencia celda por
celda está en `mapeo_form_bce.md` (raíz del proyecto) y el lector en `app/form_bce.py`.

---

## 🐍 Python Client Example

```python
import requests

API_URL = "http://localhost:8000"

# Ejemplo 1: Predicción simple
response = requests.post(
    f"{API_URL}/predict",
    json={
        "company_id": "12345678-9",
        "features": {
            "TOTAL ACTIVO": 5000000,
            "TOTAL PASIVO": 3000000,
            "TOTAL PATRIMONIO": 2000000,
            "ROA": 0.15,
            "ROE": 0.22,
            "Capital": 500000
        },
        "explain": False
    }
)

result = response.json()
print(f"Score: {result['score']}")
print(f"Rating: {result['risk_rating']['category']}")
print(f"Probabilidad: {result['probability']:.2%}")

# Decisión automática
if result['score'] >= 650:
    print("✅ APROBAR préstamo")
elif result['score'] >= 500:
    print("⚠️  APROBAR con condiciones especiales")
else:
    print("❌ RECHAZAR préstamo")
```

---

## 🧪 Testing

```bash
# Test automatizado
python test_api_simple.py

# Test manual desde Swagger UI
# Abrir: http://localhost:8000/docs
# Click en endpoint → "Try it out" → Ejecutar
```

---

## 📦 Production Deployment

### Docker

```bash
# Build
docker build -t credit-scoring-api .

# Run
docker run -d -p 8000:8000 credit-scoring-api

# Logs
docker logs -f <container_id>
```

### Con Gunicorn (Production)

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

---

## 🔧 Configuración

Editar `app/config.py` para ajustar:

- `MODEL_PATH`: Ruta al modelo .pkl
- `PDO`, `BASE_SCORE`, `BASE_ODDS`: Parámetros de scorecard
- `MAX_BATCH_SIZE`: Límite de empresas por batch
- `DEBUG`: True para development, False para production

---

## 📊 Métricas del Modelo

```
Test AUC:    0.9103  (Elite)
Test KS:     0.7105  (Exceptional)
Test Gini:   0.8206  (Excellent)
Overfit Gap: 5.33%   (Good)

Performance:
  • Worst 10%: 55% defaultearán
  • Best 10%: 1.5% defaultearán
  • Separación: 38x
```

---

## 🎓 Para la Tesis

Esta API demuestra:
- ✅ Implementación production-ready
- ✅ Software engineering best practices
- ✅ Integración con sistemas externos
- ✅ Explainability regulatoria (LIME)
- ✅ Valor agregado vs solo notebook académico

**Capítulos de tesis impactados:**
- Implementación
- Resultados
- Deployment
- Conclusiones & Trabajo Futuro

---

## 📝 Notas

- Todas las features son **opcionales** - missing values manejados por SimpleImputer
- Validación suave de coherencia contable (warnings, no errors)
- LIME puede ser costoso computacionalmente - usar solo cuando necesario
- Para producción, considerar: rate limiting, authentication, monitoring

---

## 🆘 Troubleshooting

**Error: "Modelo no cargado"**
```bash
# Verificar que artifacts existen:
ls -lh artifacts/

# Si no, ejecutar:
python ../export_artifacts_for_api.py
```

**Error: "ModuleNotFoundError: No module named 'app'"**
```bash
# Ejecutar desde credit-scoring-api/ directory
cd credit-scoring-api
uvicorn app.main:app --reload
```

**Error: "Port 8000 already in use"**
```bash
# Cambiar puerto:
uvicorn app.main:app --reload --port 8001
```

---

## 📧 Contact

[Tu nombre]  
[Tu email]  
[Universidad]

