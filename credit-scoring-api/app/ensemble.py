"""EnsemblePredictor: wrapper que combina varios modelos (Pipeline).

Expone la interfaz sklearn-like (`predict_proba`) para ser drop-in compatible
con `predictor.py`, que espera un unico objeto con ese metodo.

La clase se serializa con joblib desde `export_artifacts_for_api.py`. Para que
joblib.load la deserialice correctamente, esta misma definicion debe ser
importable bajo el mismo modulo (`app.ensemble.EnsemblePredictor`) tanto en
serializacion (export script) como en deserializacion (API runtime).
"""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class PipelineCompletoAdapter:
    """Envuelve un pipeline de scikit-learn con todo el preprocesamiento adentro.

    El pipeline se ajusto sobre todas las variables candidatas (`input_columns`) y su selector se
    queda con las que usa el modelo (`features`). El API solo envia esas variables: las demas se
    completan como vacias, el imputador del pipeline las rellena y el selector las descarta, asi que
    no cambian la prediccion. El modulo de los transformadores (`pipeline_cv`) tiene que ser
    importable al deserializar (ver `app/predictor.py`).
    """

    def __init__(self, pipeline, input_columns: List[str], features: List[str]):
        self.pipeline = pipeline
        self.input_columns = list(input_columns)
        self.features = list(features)
        self.feature_names_in_ = list(features)

    def predict_proba(self, X) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.features)
        X_full = X.reindex(columns=self.input_columns).replace([np.inf, -np.inf], np.nan).astype("float64")
        return self.pipeline.predict_proba(X_full)

    def __repr__(self) -> str:
        return (f"PipelineCompletoAdapter({type(self.pipeline[-1]).__name__}, "
                f"{len(self.features)} de {len(self.input_columns)} variables)")


class EnsemblePredictor:
    """Combina varios modelos con pesos para producir P(default).

    Cada miembro fue entrenado sobre su propio subset de features. En tiempo de
    prediccion, este wrapper:
      1. Recibe X con la union de features.
      2. Para cada miembro: slice del DataFrame con sus features, llama predict_proba.
      3. Combina las probabilidades con `weights[member] * proba_member`.

    Cada miembro puede incluir un campo opcional `outlier_limits` con los
    limites de clipping (IQR / Winsor / Z-score) calculados durante el
    entrenamiento; cuando esta presente, el wrapper reaplica el mismo clipping
    a la entrada antes de llamar a predict_proba del miembro, garantizando
    coherencia distribucional entre training y serving.

    `preprocessing` puede incluir `imputation_medians` (dict col -> mediana,
    fit en train): los NaN se imputan con esas medianas ANTES del clipping,
    reproduciendo el orden exacto del pipeline de evaluacion del notebook
    (inf->NaN -> mediana -> clip -> pipeline del miembro).
    """

    def __init__(
        self,
        members: Dict[str, Dict],
        weights: Dict[str, float],
        method: str = "simple",
        features_union: Optional[List[str]] = None,
        threshold: Optional[float] = None,
        label: Optional[str] = None,
        preprocessing: Optional[Dict] = None,
    ):
        self.members = members
        self.weights = weights
        self.method = method
        self.features_union = features_union or []
        self.threshold = threshold
        self.label = label or "Ensemble"
        self.preprocessing = preprocessing or {}
        self.feature_names_in_ = list(self.features_union)
        self.member_names = list(members.keys())

    @staticmethod
    def _apply_outlier_limits(X: pd.DataFrame, limits: Optional[Dict]) -> pd.DataFrame:
        """Reaplica los limites del outlier treatment a la entrada X."""
        if limits is None:
            return X
        cols = limits.get("columns") or list(X.columns)
        lo = np.asarray(limits["lo"], dtype=np.float64)
        hi = np.asarray(limits["hi"], dtype=np.float64)
        X_aligned = X.reindex(columns=cols)
        clipped = np.clip(X_aligned.values.astype(np.float64), lo, hi)
        return pd.DataFrame(clipped, index=X.index, columns=cols)

    def predict_proba(self, X) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.features_union)

        agg = np.zeros(len(X), dtype=float)
        for name, info in self.members.items():
            cols = info["features"]
            X_member = X.copy()
            for c in cols:
                if c not in X_member.columns:
                    X_member[c] = np.nan
            X_member = X_member[cols]

            # Mismo orden que en la evaluacion del notebook:
            # 1) inf -> NaN
            X_member = X_member.replace([np.inf, -np.inf], np.nan).apply(pd.to_numeric, errors="coerce")

            # 2) Imputacion por mediana (fit en train), serializada con el modelo
            medians = (getattr(self, "preprocessing", None) or {}).get("imputation_medians")
            if medians and X_member.isna().any().any():
                X_member = X_member.fillna(
                    {c: medians[c] for c in X_member.columns if c in medians}
                )

            # 3) Reaplicar el clipping de outliers del entrenamiento
            X_member = self._apply_outlier_limits(X_member, info.get("outlier_limits"))

            # 3b) Discretizacion por deciles (si el miembro fue entrenado con
            # ella): mismos (SimpleImputer, KBinsDiscretizer) fit en train,
            # aplicados post-clipping — identico al path de evaluacion.
            dts = info.get("decile_transformers")
            if dts:
                for c in X_member.columns:
                    if c in dts:
                        imp_c, disc_c = dts[c]
                        X_member[c] = disc_c.transform(imp_c.transform(X_member[[c]])).ravel()

            # 4) Imputacion defensiva residual (solo columnas sin mediana
            # serializada, p.ej. payloads legacy sin `preprocessing`).
            if X_member.isna().any().any():
                X_member = X_member.fillna(0)

            proba = info["modelo"].predict_proba(X_member)[:, 1]

            agg += self.weights[name] * proba

        return np.column_stack([1.0 - agg, agg])

    def __repr__(self) -> str:
        return (
            f"EnsemblePredictor(label={self.label!r}, method={self.method!r}, "
            f"members={list(self.members.keys())}, weights={self.weights})"
        )
