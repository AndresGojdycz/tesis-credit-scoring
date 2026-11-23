import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List
import logging

from app.config import settings
from app.feature_engineering import completar_derivadas
from app.macro import completar_macro
from app.models import CompanyFeatures, RiskRating

logger = logging.getLogger(__name__)


class CreditScoringPredictor:
    """Predictor de credit scoring"""

    # Fallback si model_card.json no esta disponible (cortes ascendentes t1<t2<t3)
    DEFAULT_SCORECARD_THRESHOLDS = [730, 800, 890]

    def __init__(self):
        self.model = None
        self.feature_names = None
        self.model_loaded = False
        self.scorecard_thresholds = list(self.DEFAULT_SCORECARD_THRESHOLDS)
        self.ohe_categories = dict(self.OHE_CATEGORIES)

    def load_model(self):
        """Carga el modelo y artifacts"""
        try:
            logger.info(f"Cargando modelo desde {settings.MODEL_PATH}")
            # El pipeline del modelo usa los transformadores de pipeline_cv (imputacion, seleccion,
            # outliers, deciles, escalado), serializados con ese nombre de modulo desde el notebook.
            import sys
            from app import pipeline_cv as _pipeline_cv
            sys.modules.setdefault("pipeline_cv", _pipeline_cv)
            self.model = joblib.load(settings.MODEL_PATH)

            # Cargar feature names si existen
            if settings.FEATURE_NAMES_PATH.exists():
                self.feature_names = joblib.load(settings.FEATURE_NAMES_PATH)
            else:
                # Inferir del modelo
                self.feature_names = self._get_feature_names_from_model()

            # Cortes del scorecard desde model_card.json (fuente unica de verdad,
            # regenerado por export_artifacts_for_api.py en cada export)
            self._load_scorecard_thresholds()

            # Categorias OHE derivadas de feature_names (fuente de verdad del
            # modelo) — evita desincronizacion con listas hardcodeadas
            self.ohe_categories = self._derive_ohe_categories()

            self.model_loaded = True
            logger.info(f"Modelo cargado exitosamente. Features: {len(self.feature_names)}")

        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            raise RuntimeError(f"No se pudo cargar el modelo: {e}")

    def _load_scorecard_thresholds(self):
        """Lee los cortes de banda del model_card.json exportado junto al modelo."""
        import json
        card_path = settings.ARTIFACTS_DIR / "model_card.json"
        try:
            with open(card_path) as f:
                card = json.load(f)
            thresholds = (card.get("scorecard") or {}).get("thresholds")
            if thresholds and len(thresholds) == 3:
                self.scorecard_thresholds = sorted(int(t) for t in thresholds)
                logger.info(f"Cortes de scorecard cargados: {self.scorecard_thresholds}")
            else:
                logger.warning(
                    f"model_card.json sin scorecard.thresholds validos; "
                    f"usando fallback {self.scorecard_thresholds}"
                )
        except Exception as e:
            logger.warning(
                f"No se pudo leer {card_path} ({e}); "
                f"usando cortes fallback {self.scorecard_thresholds}"
            )
    
    def _get_feature_names_from_model(self) -> List[str]:
        """Extrae feature names del pipeline"""
        try:
            # Si el modelo es un CalibratedClassifierCV
            if hasattr(self.model, 'calibrated_classifiers_'):
                base_estimator = self.model.calibrated_classifiers_[0].estimator
            else:
                base_estimator = self.model
            
            # Si es un Pipeline
            if hasattr(base_estimator, 'named_steps'):
                imputer = base_estimator.named_steps.get('imputer')
                if imputer and hasattr(imputer, 'feature_names_in_'):
                    return list(imputer.feature_names_in_)
            
            # Fallback
            return [f"feature_{i}" for i in range(82)]
            
        except Exception as e:
            logger.warning(f"No se pudieron extraer feature names: {e}")
            return [f"feature_{i}" for i in range(82)]
    
    # Categorias OHE conocidas por el modelo (determinadas en train).
    # Las claves del dict son las que se leen del input; el modelo espera columnas
    # con el prefijo `<clave>_<categoria>`. Para tamaño_EMPRESA la clave usa la
    # ortografia con tilde y minuscula porque asi salieron las columnas del notebook.
    OHE_CATEGORIES = {
        'TIPO_SOCIEDAD': ['Otros', 'Sociedad Anonima', 'Sociedad de Hecho',
                          'Sociedad de Resp. Limitada', 'Unipersonal'],
        'ACTIVIDAD_ECONOMICA': [
            'CONST.DE EDIFICIOS COMPLET. O DE PARTES.OBR. DE ING.CIV',
            'CUL.DE PROD.AGRI.EN COMB.CON CRIA DE ANIM. EXPLOT.MIXTA',
            'EXPLOTACION GANADERA (EXCEPTO LECHERIA)', 'EXPLOTACION LECHERA',
            'OTRAS ACTIVIDADES DE SERVICIOS N.C.P.',
            'OTROS TIPOS DE VTA. AL POR MENOR NO REALIZ. EN ALMACEN.', 'Otros',
            'TRANSPORTE DE CARGA POR CARRETERA',
            'VENTA AL POR MAYOR DE ALIMENTOS, BEBIDAS Y TABACO',
            'VENTA AL POR MAYOR DE OTROS PRODUCTOS',
            'VTA. MENOR ALMAC NO ESPECIALI.,DE ALIM.,BEB. TAB',
            'VTA.X MENOR DE ALIM.,BEB.Y TABACO EN ALMACEN. ESPECIAL.',
            'VTA.X MENOR DE APARATOS,ARTICUL.Y EQUIPO USO DOMESTIC.',
            'VTA.X MENOR DE ART.DE FERRETE.,PINTUR. Y PROD.DE VIDRIO',
            'VTA.X MENOR DE OTROS PRODUCTOS DE ALMACENES ESPECIALIZ.',
            'VTA.X MENOR DE PROD.TEXTIL.,PRENDAS,CALZ. Y ARTIC.CUERO'],
        'tamaño_EMPRESA': ['Microempresa', 'Pequena', 'Mediana', 'Grande'],
        'SECTOR': ['Agro', 'Empresas'],
    }

    def _derive_ohe_categories(self) -> Dict[str, List[str]]:
        """Deriva las categorias OHE desde feature_names — la fuente de verdad
        de lo que el modelo espera. Elimina la clase de bugs por listas
        hardcodeadas desincronizadas (categorias fantasma / faltantes)."""
        cats = {}
        for cat_col in self.OHE_CATEGORIES:
            prefix = f"{cat_col}_"
            vals = [f[len(prefix):] for f in self.feature_names if f.startswith(prefix)]
            if vals:
                cats[cat_col] = vals
        if not cats:
            # El modelo no usa ninguna dummy cualitativa (p. ej. la LR de 2026-10):
            # no se generan columnas OHE ni avisos sobre cualitativas no informadas.
            logger.info("El modelo no usa variables cualitativas (sin columnas OHE)")
            return {}
        for cat_col, vals in cats.items():
            logger.info(f"OHE {cat_col}: {len(vals)} categorias derivadas del modelo")
        return cats

    def _sanitize_input(self, features_dict: Dict) -> pd.DataFrame:
        """Sanitiza input para el modelo, incluyendo OHE dinamico"""
        # Ratios y primera_observacion que el cliente no envio (A10/A11): mismas
        # formulas que el entrenamiento; vale para /predict, batch y LIME.
        # Macro (PIB de la industria, desempleo y variaciones) desde la fecha de cierre y la actividad
        features_dict = completar_macro(features_dict)
        features_dict = completar_derivadas(features_dict)
        df = pd.DataFrame([features_dict])
        df = df.replace([np.inf, -np.inf], np.nan)

        # OHE para variables cualitativas (categorias derivadas del modelo)
        for cat_col, categories in self.ohe_categories.items():
            value = features_dict.get(cat_col)
            for cat in categories:
                ohe_col = f"{cat_col}_{cat}"
                if value and str(value) == cat:
                    df[ohe_col] = 1
                else:
                    df[ohe_col] = 0
            # Si el valor no esta en las categorias conocidas, mapear a "Otros"
            if value and str(value) not in categories and 'Otros' in categories:
                df[f"{cat_col}_Otros"] = 1

        # Asegurar que tiene todas las features necesarias
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = np.nan

        # Ordenar columnas como espera el modelo
        df = df[self.feature_names]

        # Winsorization se aplica internamente en el pipeline del modelo
        return df
    
    def predict(self, features: CompanyFeatures) -> Dict:
        """Realiza predicción"""
        if not self.model_loaded:
            raise RuntimeError("Modelo no cargado. Llama a load_model() primero.")
        
        try:
            # Convertir Pydantic a dict
            features_dict = features.dict(by_alias=True)
            
            # Sanitizar
            X = self._sanitize_input(features_dict)

            # Advertencias de imputacion: las features no informadas entran como
            # NaN y el modelo las imputa con la mediana de entrenamiento. La
            # prediccion es valida pero menos especifica — se informa al usuario.
            missing = [c for c in X.columns[X.iloc[0].isna()]]
            warnings_list = []
            if missing:
                # Las partidas de largo plazo llevan el sufijo ".1" en el balance
                nombres = [
                    c[:-2] + " (largo plazo)" if c.endswith(".1") else c
                    for c in missing
                ]
                listado = ", ".join(nombres[:10])
                if len(nombres) > 10:
                    listado += f" y {len(nombres) - 10} más"
                warnings_list.append(
                    f"{len(missing)} de {len(self.feature_names)} variables no "
                    f"informadas, imputadas con la mediana de entrenamiento: {listado}."
                )
                logger.warning(f"Predicción con {len(missing)} features imputadas")

            # Cualitativas sin informar: sus dummies quedan en 0 (ninguna
            # categoria activa), un patron no visto en entrenamiento.
            cualitativas_missing = [
                cat for cat in self.ohe_categories
                if features_dict.get(cat) in (None, "")
            ]
            if cualitativas_missing:
                warnings_list.append(
                    "Variables cualitativas no informadas (dummies en 0): "
                    + ", ".join(cualitativas_missing)
                )

            # Predecir
            probability = self.model.predict_proba(X)[:, 1][0]

            # Convertir a score
            score = self._proba_to_score(probability)

            # Asignar rating
            risk_rating = self._assign_rating(score)

            return {
                "probability": float(probability),
                "score": int(score),
                "risk_rating": risk_rating,
                "warnings": warnings_list or None,
            }
            
        except Exception as e:
            logger.error(f"Error en predicción: {e}")
            raise ValueError(f"Error procesando predicción: {e}")
    
    def predict_batch(self, features_list: List[CompanyFeatures]) -> List[Dict]:
        """Predicción batch"""
        results = []
        for features in features_list:
            try:
                result = self.predict(features)
                results.append(result)
            except Exception as e:
                # En batch, registrar error pero continuar
                logger.error(f"Error en predicción batch: {e}")
                results.append({
                    "error": str(e),
                    "probability": None,
                    "score": None,
                    "risk_rating": None
                })
        return results
    
    def _proba_to_score(self, probability: float) -> float:
        """Convierte probabilidad a score"""
        probability = np.clip(probability, 1e-6, 1 - 1e-6)
        odds = (1 - probability) / probability
        
        factor = settings.PDO / np.log(2)
        score = settings.BASE_SCORE + factor * np.log(odds)
        return np.clip(score, 0, 1500)
    
    def _assign_rating(self, score: float) -> RiskRating:
        """Asigna banda de rating segun el score crediticio (nombres y nivel de riesgo de la Tabla 6 de la tesis).

        Cuatro bandas derivadas en el notebook combinado buscando los tres
        cortes que maximizan el Information Value (IV) — metrica estandar en
        credit scoring (Siddiqi, 2017) — sujetos a monotonia en DR. Los cortes
        se fitean sobre probabilidades out-of-fold de train y se validan en
        test; los valores vigentes se leen de model_card.json
        (scorecard.thresholds y default_rates_observed_test).
        """
        t1, t2, t3 = self.scorecard_thresholds
        if score >= t3:
            return RiskRating(
                category="Bueno",
                description="Riesgo mínimo",
                color="green",
            )
        elif score >= t2:
            return RiskRating(
                category="Aceptable",
                description="Riesgo bajo",
                color="yellow",
            )
        elif score >= t1:
            return RiskRating(
                category="Comprometido",
                description="Riesgo moderado",
                color="orange",
            )
        else:
            return RiskRating(
                category="Crítico",
                description="Riesgo alto",
                color="red",
            )


# Instancia global (singleton)
predictor = CreditScoringPredictor()
