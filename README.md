# Credit Scoring — Tesis de Maestría en Ciencia de Datos

**Autor:** Andrés Gojdycz
**Año:** 2026
**Institución:** Universidad de Montevideo, Maestría en Ciencia de Datos

Sistema de credit scoring para predicción de default empresarial en Uruguay, basado en los estados contables presentados al BROU y en la Central de Riesgos del BCU. Combina un modelo de Machine Learning (Random Forest), una API REST de inferencia y un dashboard web para uso del analista de crédito.

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

## Qué NO está incluido (y por qué)

- **`data/`** — Datos de clientes del BROU. No se distribuyen por confidencialidad.
- **Archivos `.pkl`** — El repositorio no incluye el modelo del API (`credit-scoring-api/artifacts/model.pkl` y `feature_names.pkl`), las predicciones fuera de muestra de la búsqueda (`notebooks/results/pipecv/oof_*.pkl`) ni la muestra de entrenamiento para LIME (`lime_training_data.pkl`). Se regeneran al correr el notebook y `export_artifacts_for_api.py`. Sin `model.pkl` el API no arranca, y sin las predicciones fuera de muestra la búsqueda de estrategias debe correrse completa (`EXPLORAR_PIPECV = True`, unas 3 horas).
  - La copia entregada en `.zip` sí incluye el modelo del API y las predicciones fuera de muestra. No incluye la muestra de LIME, porque contiene filas de datos reales.
- **`.venv/` y `code/node_modules/`** — Entornos de dependencias regenerables. Ver instrucciones de setup abajo.
- **`.env`** — Contiene credenciales (API keys de OpenAI). Se incluye `credit-scoring-api/.env.example` con las variables vacías como referencia.

---

## Resumen de la metodología

- **Datos:** 5.843 balances anuales de 3.179 empresas (empresas y agropecuario), con cierres entre 11/2019 y 07/2022: 4.690 en entrenamiento y 1.153 en test, partidos por empresa.
- **Variable objetivo (`DEFAULT_FUTURE`):** vale 1 si en algún mes de los 12 posteriores al cierre del balance, [t+1, t+12], la empresa registra en cualquier institución un crédito vencido, en gestión, moroso o castigado por atraso (atraso de 60 días o más). Se excluyen los balances de empresas que ya estaban calificadas en 3, 4 o 5 al cierre y los de actividades financieras, y se exige la ventana de 12 meses observada completa. Tasa de default: 7,80% (456 eventos).
- **Búsqueda:** cinco modelos (regresión logística, árbol de decisión, Random Forest, XGBoost y MLP) con 140 estrategias de preprocesamiento cada uno (outliers × transformación × selección de variables × balanceo), evaluadas con validación cruzada GroupKFold(5) por empresa y el pipeline completo ajustado en cada partición. Exploración con RandomizedSearchCV y ajuste fino de la mejor estrategia de cada modelo.
- **Selección:** la estrategia de cada modelo, por AUC de validación cruzada tras el ajuste fino; el modelo, por mayor AUC de entrenamiento del modelo final reentrenado con todo el conjunto de entrenamiento.
- **Modelo elegido:** Random Forest con recorte de outliers por IQR, transformación Yeo-Johnson, 107 variables seleccionadas por RFECV y sin resampling.
- **Desempeño:** AUC de validación cruzada 0,688; de entrenamiento 0,825; de test 0,751 (IC95 0,694 a 0,802), con KS de 0,449. Umbral operativo de 0,0835 (promedio de los umbrales de máxima separación KS de cada partición): en test detecta 63 de los 80 defaults (recall 78,8%, precisión 13,3%).
- **Scorecard:** puntaje con PDO = 50 y base 600; 4 bandas (Crítico, Comprometido, Aceptable y Bueno) con cortes en 722, 762 y 792, elegidos maximizando el Information Value sobre las probabilidades fuera de muestra de entrenamiento. La tasa de default baja en forma monótona en entrenamiento (21,4% a 3,7%); en test, la banda Crítico (37 balances, 3 defaults) queda por debajo de Comprometido.
- **Serving = evaluación:** el modelo serializado incluye el preprocesamiento completo, ajustado en entrenamiento; el AUC del artefacto recargado reproduce el AUC evaluado en el notebook.
- **Explicabilidad:** LIME para las explicaciones locales del API, con resúmenes en lenguaje natural generados por OpenAI; en el notebook, SHAP (TreeSHAP) como contraste para un caso.



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
