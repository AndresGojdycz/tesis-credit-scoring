# Credit Scoring — Tesis de Maestría en Ciencia de Datos

**Autor:** Andrés Gojdycz
**Año:** 2026
**Institución:** Universidad de Montevideo, Maestría en Ciencia de Datos

Sistema de credit scoring corporativo en Uruguay, basado en los estados contables presentados al BROU y en la Central de Riesgos del BCU. Combina un modelo de Machine Learning (Random Forest) y un dashboard web para uso del analista de crédito.

---

## Estructura del proyecto

```
.
├── Tesis Andres Gojdycz.pdf       Trabajo escrito (versión de entrega)
├── notebooks/                    Notebook de modelado y EDA
│   ├── modelo_combinado_narrativa.ipynb   Notebook principal (modelado, scorecard, figuras de la tesis)
│   ├── pipeline_cv.py           Preprocesamiento dentro de la validación cruzada
│   ├── funciones.py             Funciones de soporte del notebook
│   ├── graficos_tesis/          Figuras de la tesis, generadas por el notebook
│   └── results/pipecv/          Resultados de la búsqueda de estrategias (CSV)
├── datos macro/                  Series macroeconómicas públicas (desempleo, PIB, Unidad Indexada)
├── credit-scoring-api/           API REST (FastAPI) que sirve el modelo
│   ├── app/                     Código de la aplicación
│   ├── artifacts/               Modelo serializado, metadata (model_card.json) y series macro (macro.json)
│   ├── Dockerfile               Container de producción
│   └── requirements.txt         Dependencias del container Docker
├── code/                         Dashboard web (Next.js + TypeScript)
├── ejemplos/                     Formularios de estados contables de ejemplo, uno por banda de riesgo
│   └── formulario_bce/          .xlsx listos para importar en el dashboard
├── export_artifacts_for_api.py   Script para exportar artefactos del notebook → API
├── export_macro_for_api.py       Script para exportar las series macro (PIB por industria, desempleo) → API
├── mapeo_form_bce.md             Mapeo del formulario de estados contables del BROU a las variables del modelo
├── diccionario.md                Diccionario de variables
├── pyproject.toml                Dependencias Python (gestionadas con uv)
└── uv.lock                       Lock file para reproducibilidad exacta
```

---

> `data/` no está incluido: son datos de clientes del BROU y no se distribuyen por confidencialidad.

---

## Metodología

- **Datos:** 5.843 balances anuales de 3.179 empresas (cierres entre 11/2019 y 07/2022), partidos por empresa en entrenamiento (4.690) y test (1.153).
- **Variable objetivo:** atraso de 60 días o más en cualquier institución en los 12 meses posteriores al cierre del balance.
- **Búsqueda:** cinco modelos (regresión logística, árbol de decisión, Random Forest, XGBoost y MLP) con 140 estrategias de preprocesamiento cada uno, evaluadas con validación cruzada GroupKFold(5) por empresa.
- **Modelo elegido:** Random Forest con recorte de outliers por IQR, transformación Yeo-Johnson y 107 variables seleccionadas por RFECV.
- **Desempeño en test:** AUC 0,751 (IC95 0,694 a 0,802) y KS 0,449, con umbral operativo de 0,0835.
- **Scorecard:** PDO = 50 y base 600, con 4 bandas (Crítico, Comprometido, Aceptable y Bueno) y cortes en 722, 762 y 792.
- **Explicabilidad:** LIME en el API y SHAP en el notebook.

---

## Cómo reproducir el sistema

### 1. Backend (API FastAPI)

Requiere Python ≥ 3.13, [uv](https://docs.astral.sh/uv/) instalado y el modelo en `credit-scoring-api/artifacts/` (`model.pkl` y `feature_names.pkl`).

```bash
# Desde la raíz del proyecto
uv sync                                    # crea .venv e instala dependencias

cd credit-scoring-api
cp .env.example .env                       # luego editar y completar OPENAI_API_KEY
uv run uvicorn app.main:app --reload
```

API disponible en http://localhost:8000. Documentación interactiva en http://localhost:8000/docs.

Endpoints principales:
- `POST /predict` — predicción individual; con `?explain=true` agrega la explicación LIME (requiere `artifacts/lime_training_data.pkl`)
- `POST /predict/batch` — predicción batch (hasta 100 empresas)
- `POST /importar/form-bce` — lee el formulario de estados contables del BROU (.xlsx) y devuelve los campos del dashboard; hay ejemplos en `ejemplos/formulario_bce/`
- `GET /model/info` — metadata del modelo (lee de `artifacts/model_card.json`)
- `GET /health` — health check

### 2. Frontend (Dashboard)

Requiere Node.js ≥ 20.9 (lo exige Next.js 16) y el API corriendo en http://localhost:8000.

```bash
cd code
npm install
npm run dev
```

Dashboard disponible en http://localhost:3000.

### 3. Container Docker (opcional)

```bash
cd credit-scoring-api
docker build -t credit-scoring-api .
docker run -p 8000:8000 --env-file .env credit-scoring-api
```

### 4. Re-ejecutar el notebook

Requiere acceso a los datos del BROU (no incluidos en el repositorio, por confidencialidad).

```bash
# Con los datos ubicados en data/:
uv sync
uv run jupyter notebook notebooks/modelo_combinado_narrativa.ipynb
```

Tras correr el notebook, regenerar los artefactos para la API:

```bash
uv run python export_artifacts_for_api.py
uv run python export_macro_for_api.py
```

El segundo script arma `macro.json` a partir de `datos macro/`, con los mismos pasos del notebook. Con la fecha de cierre del balance y la actividad económica, el API completa el PIB de la industria, el desempleo y sus variaciones.

---

## Documentos clave para la lectura

| Archivo | Para qué |
|---------|----------|
| `notebooks/modelo_combinado_narrativa.ipynb` | Modelado paso a paso, EDA, scorecard y figuras de la tesis |
| `credit-scoring-api/artifacts/model_card.json` | Especificación del modelo desplegado |
| `diccionario.md` | Diccionario de las features del modelo |

---

## Contacto

Andrés Gojdycz — andgojdycz@gmail.com
