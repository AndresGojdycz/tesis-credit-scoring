import numpy as np
import pandas as pd
from lime.lime_tabular import LimeTabularExplainer
from typing import Dict, List, Optional
import logging

from app.config import settings
from app.predictor import predictor

logger = logging.getLogger(__name__)


class LIMEExplainerService:
    """Servicio de explicaciones LIME"""

    def __init__(self):
        self.explainer = None
        self.training_data = None
        self._openai_client = None

    def initialize(self, training_data: np.ndarray = None):
        """Inicializa LIME explainer.

        Carga la muestra de training serializada desde artifacts/lime_training_data.pkl,
        que LIME necesita para calcular percentiles de discretizacion y dimensionar
        las perturbaciones de las explicaciones locales. Si el archivo no existe o
        tiene shape inconsistente con el modelo, falla explicitamente — no se usa
        fallback sintetico.
        """
        try:
            if training_data is None:
                training_data = self._load_lime_training_data()

            self.training_data = training_data

            self.explainer = LimeTabularExplainer(
                training_data=training_data,
                feature_names=predictor.feature_names,
                class_names=['No Default', 'Default'],
                mode='classification',
                discretize_continuous=True,
                random_state=42
            )

            logger.info("LIME explainer inicializado")

            # Inicializar cliente OpenAI si hay API key
            if settings.OPENAI_API_KEY:
                try:
                    from openai import OpenAI
                    self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                    logger.info("OpenAI client inicializado para resúmenes LIME")
                except Exception as e:
                    logger.warning(f"No se pudo inicializar OpenAI client: {e}")
            else:
                logger.info("OPENAI_API_KEY no configurada, resúmenes LIME deshabilitados")

        except Exception as e:
            logger.error(f"Error inicializando LIME: {e}")
            raise

    def explain_prediction(self, features_dict: Dict, num_features: int = 10,
                           probability: float = None, score: int = None,
                           risk_rating: str = None) -> Dict:
        """Genera explicación LIME con resumen en lenguaje natural opcional"""
        if self.explainer is None:
            raise RuntimeError("LIME no inicializado")

        try:
            # Preparar input y aplicar la MISMA imputacion que el modelo
            # (medianas de train serializadas): LIME debe perturbar alrededor
            # del punto que el modelo efectivamente evalua, no de un vector con
            # NaN que el modelo nunca ve. El clipping/YJ/calibracion posteriores
            # viven dentro de predict_proba y aplican igual a las perturbaciones.
            X = predictor._sanitize_input(features_dict)
            X = X.replace([np.inf, -np.inf], np.nan)
            medians = (getattr(predictor.model, "preprocessing", None) or {}).get(
                "imputation_medians", {}
            )
            if medians:
                X = X.fillna({c: medians[c] for c in X.columns if c in medians})
            if X.iloc[0].isna().any():
                # Residual (features sin mediana serializada): mediana de la
                # muestra de entrenamiento de LIME
                med_td = np.nanmedian(self.training_data, axis=0)
                X = X.fillna(pd.Series(med_td, index=X.columns))
            instance = np.array(X.values[0], dtype=np.float64)

            # Generar explicación
            explanation = self.explainer.explain_instance(
                instance,
                predictor.model.predict_proba,
                num_features=num_features
            )

            # Extraer información: se muestra solo el nombre de la variable; la
            # condicion de LIME (p. ej. "ROE <= 0.10") queda para el resumen
            condiciones = dict(explanation.as_list())
            top_features = []
            for (indice, contrib), condicion in zip(explanation.as_map()[1], condiciones):
                nombre = X.columns[indice]
                # Las partidas de largo plazo llevan el sufijo ".1" en el balance
                if nombre.endswith(".1"):
                    nombre = nombre[:-2] + " (largo plazo)"
                top_features.append({
                    "feature": nombre,
                    "contribution": float(contrib),
                    "condicion": condicion,
                })

            # Predicción local del modelo lineal de LIME
            local_pred = explanation.local_pred[0] if hasattr(explanation, 'local_pred') else None
            intercept = explanation.intercept[1] if hasattr(explanation, 'intercept') else 0.0

            # Generar resumen en lenguaje natural
            summary = self._generate_summary(
                top_features=top_features,
                probability=probability,
                score=score,
                risk_rating=risk_rating,
            )

            return {
                "top_features": top_features,
                "prediction": float(local_pred) if local_pred is not None else None,
                "intercept": float(intercept),
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error generando explicación: {e}")
            raise ValueError(f"Error en explicación LIME: {e}")

    def _generate_summary(self, top_features: List[Dict],
                          probability: float = None, score: int = None,
                          risk_rating: str = None) -> Optional[str]:
        """Genera resumen en lenguaje natural usando OpenAI"""
        if self._openai_client is None:
            return None

        try:
            # Formatear features para el prompt
            features_text = "\n".join(
                f"- {f['condicion']}: {'aumenta' if f['contribution'] > 0 else 'disminuye'} riesgo ({f['contribution']:+.4f})"
                for f in top_features[:8]
            )

            user_message = (
                f"Score crediticio: {score}\n"
                f"Rating: {risk_rating}\n"
                f"Probabilidad de default: {probability:.2%}\n\n"
                f"Factores principales (LIME):\n{features_text}"
            )

            response = self._openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un analista de riesgo crediticio. Escribe un resumen de 2-3 oraciones en español "
                            "explicando los factores clave que determinaron el score crediticio de esta empresa. "
                            "Usa lenguaje claro y profesional para un analista de crédito. "
                            "No repitas los números exactos del score ni la probabilidad, enfócate en los factores."
                        ),
                    },
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Error generando resumen OpenAI: {e}")
            return None

    def _load_lime_training_data(self) -> np.ndarray:
        """Carga la muestra de training serializada para inicializar LIME.

        Falla explicitamente si el archivo no existe o tiene shape inconsistente
        con el modelo, en lugar de generar datos sinteticos. La explicabilidad
        requiere datos reales del entrenamiento para producir explicaciones
        fidedignas.
        """
        import joblib as _joblib
        n_features = len(predictor.feature_names)
        lime_data_path = settings.ARTIFACTS_DIR / "lime_training_data.pkl"

        if not lime_data_path.exists():
            raise FileNotFoundError(
                f"No se encontro {lime_data_path}. LIME requiere la muestra de "
                f"training serializada durante el entrenamiento. Re-ejecutar "
                f"export_artifacts_for_api.py para regenerar el artefacto."
            )

        data = _joblib.load(lime_data_path)
        if not hasattr(data, 'shape') or data.shape[1] != n_features:
            actual_shape = getattr(data, 'shape', 'desconocido')
            raise ValueError(
                f"lime_training_data.pkl tiene shape {actual_shape} pero el modelo "
                f"espera {n_features} features. Regenerar el artefacto con "
                f"export_artifacts_for_api.py despues de re-entrenar el modelo."
            )

        logger.info(f"LIME training data cargado: {data.shape}")
        return np.asarray(data, dtype=np.float64)


# Instancia global
lime_explainer = LIMEExplainerService()
