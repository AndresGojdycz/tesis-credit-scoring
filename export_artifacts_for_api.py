"""
Exportar artefactos del modelo ganador para la API.

Detecta automaticamente el tipo de payload (individual o ensemble) y exporta
un unico objeto compatible con el predictor de la API:
  - Individual: el Pipeline entrenado directo.
  - Ensemble:   un EnsemblePredictor que combina los miembros con sus pesos.

Ambos casos exponen .predict_proba(X) y son drop-in para predictor.py.

Ejecutar desde la raiz del proyecto:
    uv run python export_artifacts_for_api.py
"""
import sys
import joblib
import numpy as np
import shutil
from pathlib import Path

print("=" * 80)
print("EXPORTANDO ARTIFACTS PARA API (ganador unificado)")
print("=" * 80)

ROOT_DIR = Path(__file__).parent
NOTEBOOKS_DIR = ROOT_DIR / "notebooks"
API_DIR = ROOT_DIR / "credit-scoring-api"
API_ARTIFACTS_DIR = API_DIR / "artifacts"
API_ARTIFACTS_DIR.mkdir(exist_ok=True)

# La definicion de EnsemblePredictor vive en credit-scoring-api/app/ensemble.py.
# Importamos desde el path de la API para que joblib pueda localizar la clase
# al deserializar (mismo modulo path: app.ensemble.EnsemblePredictor).
sys.path.insert(0, str(API_DIR))
from app.ensemble import EnsemblePredictor, PipelineCompletoAdapter  # noqa: E402
# El pickle del notebook referencia el modulo pipeline_cv (transformadores del pipeline completo)
sys.path.insert(0, str(NOTEBOOKS_DIR))

# ============================================================================
# CARGAR MODELO FINAL
# ============================================================================
src_path = NOTEBOOKS_DIR / "results" / "modelo_final.pkl"
if not src_path.exists():
    raise FileNotFoundError(
        f"No se encontro {src_path}. Corre el notebook hasta la celda de "
        f"model registry para generar modelo_final.pkl."
    )
payload = joblib.load(src_path)
key = next(iter(payload.keys()))
info = payload[key]

is_ensemble = info.get("is_ensemble", False) or key == "ENSEMBLE"
print(f"\nPayload key: {key}")
print(f"Tipo: {'ENSEMBLE' if is_ensemble else f'INDIVIDUAL ({key})'}")

# ============================================================================
# CONSTRUIR OBJETO EXPORTABLE + LISTA DE FEATURES
# ============================================================================
if is_ensemble:
    members_data = info["members"]
    weights = info["weights"]
    method = info["method"]
    label = info.get("label", "Ensemble")
    features_union = info["features_union"]
    threshold = info.get("threshold")

    print(f"\nEnsemble detectado:")
    print(f"  Label:     {label}")
    print(f"  Method:    {method}")
    print(f"  Members:   {list(members_data.keys())}")
    print(f"  Weights:   {weights}")
    print(f"  Features:  {len(features_union)} (union)")
    print(f"  Threshold: {threshold}")

    # Construir el dict que EnsemblePredictor espera (subset de fields necesarios
    # para inferencia: modelo + features + outlier_limits para reaplicar el
    # clipping de outliers usado durante el entrenamiento).
    ep_members = {
        name: {
            "modelo": m["modelo"],
            "features": list(m["features"]),
            "outlier_limits": m.get("outlier_limits"),
            "decile_transformers": m.get("decile_transformers"),
        }
        for name, m in members_data.items()
    }

    exportable = EnsemblePredictor(
        members=ep_members,
        weights=weights,
        method=method,
        features_union=features_union,
        threshold=threshold,
        label=label,
        preprocessing=info.get("preprocessing"),
    )
    feature_names = features_union
    metrics = info.get("test_metrics", {})

    scorecard_info = info.get("scorecard")
    if not scorecard_info:
        raise RuntimeError(
            "El payload no incluye 'scorecard' (cortes del scorecard). "
            "Re-ejecutar el notebook hasta la celda de model registry antes de exportar."
        )
    if not info.get("preprocessing"):
        raise RuntimeError(
            "El payload no incluye 'preprocessing' (medianas de imputacion). "
            "Re-ejecutar el notebook hasta la celda de model registry antes de exportar."
        )

else:
    print(f"\nIndividual {key} detectado:")
    print(f"  Strategy:  {info.get('strategy')}")
    print(f"  Features:  {len(info['features'])}")
    print(f"  Threshold: {info.get('threshold')}")
    print(f"  Metrics:   {info.get('metrics')}")

    # Envuelvo el modelo individual en un EnsemblePredictor de un solo miembro
    # con peso 1.0. Esto reutiliza el manejo de outlier_limits del wrapper y
    # mantiene una interfaz consistente entre exports individuales y ensemble.
    # Pipeline completo (todo el preprocesamiento adentro, 2026-11-03): se envuelve para que reciba solo
    # las variables del modelo; las medianas de esas variables se aplican antes, igual que en el notebook.
    modelo_srv = info["modelo"]
    if info.get("pipeline_completo"):
        modelo_srv = PipelineCompletoAdapter(info["modelo"], info["input_columns"], info["features"])
        print(f"  Pipeline completo: {len(info['features'])} de {len(info['input_columns'])} variables candidatas")
    exportable = EnsemblePredictor(
        members={
            key: {
                "modelo": modelo_srv,
                "features": list(info["features"]),
                "outlier_limits": info.get("outlier_limits"),
                "decile_transformers": info.get("decile_transformers"),
            }
        },
        weights={key: 1.0},
        method="single",
        features_union=list(info["features"]),
        threshold=info.get("threshold"),
        label=key,
        preprocessing=info.get("preprocessing"),
    )
    feature_names = info["features"]
    metrics = info.get("test_metrics") or info.get("metrics", {})
    scorecard_info = info.get("scorecard")
    threshold = info.get("threshold")

# ============================================================================
# 0. PARIDAD: el objeto exportado debe reproducir las probabilidades del notebook
#    sobre las entradas ORIGINALES de test (con faltantes), igual que el API.
# ============================================================================
parity = info.get("parity")
if parity is None:
    raise RuntimeError(
        "El payload no incluye 'parity'. Re-ejecutar el notebook hasta la celda "
        "de model registry antes de exportar."
    )
p_export = exportable.predict_proba(parity["X_test_raw"])[:, 1]
max_dp = float(np.abs(p_export - parity["proba_test"]).max())
print(f"\n0. Paridad notebook vs export (test, n={len(p_export)}): max|dproba| = {max_dp:.2e}")
assert max_dp < 1e-9, "El modelo exportado NO reproduce las probabilidades del notebook."

# ============================================================================
# 1. MODELO (Pipeline single OR EnsemblePredictor) -> model.pkl
# ============================================================================
print("\n1. Exportando modelo...")
model_path = API_ARTIFACTS_DIR / "model.pkl"
joblib.dump(exportable, model_path)
print(f"   Guardado: {model_path} ({model_path.stat().st_size / 1024:.0f} KB)")
# Nombre anterior del artefacto (cuando el ganador era un Random Forest)
legacy_model = API_ARTIFACTS_DIR / "rf_model.pkl"
if legacy_model.exists():
    legacy_model.unlink()
    print(f"   Borrado el artefacto anterior: {legacy_model.name}")

# ============================================================================
# 2. FEATURE NAMES -> feature_names.pkl + feature_names.txt
# ============================================================================
print("\n2. Exportando feature names...")
feat_path = API_ARTIFACTS_DIR / "feature_names.pkl"
joblib.dump(list(feature_names), feat_path)

txt_path = API_ARTIFACTS_DIR / "feature_names.txt"
with open(txt_path, "w") as f:
    for i, name in enumerate(feature_names, 1):
        f.write(f"{i}. {name}\n")

ohe_feats = [
    f for f in feature_names
    if f.startswith(("TIPO_SOCIEDAD_", "ACTIVIDAD_ECONOMICA_", "tamaño_EMPRESA_", "SECTOR_"))
]
print(f"   Guardado: {len(feature_names)} features ({len(ohe_feats)} OHE)")
print(f"   Archivo:  {feat_path}")
print(f"   Texto:    {txt_path}")

if ohe_feats:
    print(f"\n   Features OHE ({len(ohe_feats)}):")
    for f in ohe_feats:
        print(f"     {f}")

# ============================================================================
# 3. LIME TRAINING DATA (si existe)
# ============================================================================
print("\n3. LIME training data...")
lime_candidates = [
    NOTEBOOKS_DIR / "lime_training_data.pkl",
    NOTEBOOKS_DIR / "results" / "lime_training_data.pkl",
]
copied = False
for candidate in lime_candidates:
    if candidate.exists():
        shutil.copy(candidate, API_ARTIFACTS_DIR / "lime_training_data.pkl")
        print(f"   Copiado desde: {candidate}")
        copied = True
        break
if not copied:
    print("   No encontrado (la API regenerara on-demand al usar explain=true)")

# ============================================================================
# 4. MODEL CARD (fuente unica de verdad para API + frontend) -> model_card.json
# ============================================================================
import json

# Performance del modelo — todo sale del payload del notebook (sin hardcodes)
test_auc = float(metrics.get("test_auc", 0.0)) if metrics else 0.0
test_ks = float(metrics.get("test_ks", 0.0)) if metrics else 0.0

selection = info.get("selection", {})
train_auc_in_sample = selection.get("train_auc_in_sample")
overfit_gap = (
    round(float(train_auc_in_sample) - test_auc, 4)
    if train_auc_in_sample is not None else None
)

calibration = info.get("calibration")  # None = sin calibrar (estado real del modelo)
dataset_info = info.get("dataset") or {}  # muestra y target, desde el notebook

scorecard_card = None
if scorecard_info:
    scorecard_card = {
        "thresholds": [int(t) for t in scorecard_info["thresholds"]],
        "bands": list(scorecard_info["labels"]),
        "fit_sample": scorecard_info.get("fit_sample"),
        "default_rates_observed_test": {
            k: round(float(v), 4)
            for k, v in scorecard_info.get("band_default_rates_test", {}).items()
        },
        "iv_dev": round(float(scorecard_info["iv_dev"]), 4),
        # iv_test puede ser NaN (banda pura en test, p.ej. 0 defaults en Bueno):
        # NaN no es JSON valido -> se serializa como null
        "iv_test": (round(float(scorecard_info["iv_test"]), 4)
                    if scorecard_info.get("iv_test") == scorecard_info.get("iv_test")
                    else None),
        "pdo": int(scorecard_info.get("pdo", 50)),
        "base_score": int(scorecard_info.get("base_score", 600)),
        "score_range_theoretical": [0, 1500],
    }

model_card = {
    "model": {
        "type": "Ensemble" if is_ensemble else key,
        "label": label if is_ensemble else key,
        "method": method if is_ensemble else "single",
        "members": list(members_data.keys()) if is_ensemble else [key],
        "weights": {k: float(v) for k, v in weights.items()} if is_ensemble else {key: 1.0},
        "threshold_operativo": float(threshold) if threshold is not None else None,
        "threshold_origin": selection.get("threshold_origin"),
        "selection_criterion": selection.get("criterion"),
        "cv_auc_mean": (round(float(selection["cv_auc_mean"]), 4)
                        if selection.get("cv_auc_mean") is not None else None),
        "cv_auc_std": (round(float(selection["cv_auc_std"]), 4)
                       if selection.get("cv_auc_std") is not None else None),
        "version": "3.0.0",
    },
    "training": {
        "target": dataset_info.get("target"),
        "dataset": "combinado (empresas + agropecuario)",
        "n_observations": dataset_info.get("n_observations"),
        "n_companies": dataset_info.get("n_companies"),
        "default_rate_observed": dataset_info.get("default_rate"),
        "default_rate_train": dataset_info.get("default_rate_train"),
        "n_features": len(feature_names),
    },
    "performance": {
        "test_auc": test_auc,
        "test_ks": test_ks,
        "test_auc_ic95": (metrics or {}).get("test_auc_ic95"),
        "overfit_gap": overfit_gap,
    },
    "scorecard": scorecard_card,
    "preprocessing": {
        "imputation": ("Mediana de train, dentro del pipeline (las medianas de las variables del modelo "
                       "tambien se serializan y se aplican antes)"
                       if info.get("pipeline_completo") else
                       "Mediana (fit en train, medianas serializadas en el modelo)"),
        "calibration": calibration if calibration is not None
                       else "Ninguna (probabilidades del modelo sin calibrar)",
        "outlier_treatment": (f"{info.get('outlier')}, dentro del pipeline (limites ajustados en train)"
                              if info.get("pipeline_completo") else
                              "Clipping por miembro con limites fit en train, "
                              "serializados y reaplicados en serving"),
        "strategy": info.get("strategy"),
        "resampling": "Segun la estrategia elegida (ver notebook)",
    },
}

model_card_path = API_ARTIFACTS_DIR / "model_card.json"
with open(model_card_path, "w") as f:
    json.dump(model_card, f, indent=2, ensure_ascii=False)
print(f"\n4. Model card exportado: {model_card_path}")

# Compatibilidad: ensemble_meta.json (legacy, mas chico)
if is_ensemble:
    meta = {
        "is_ensemble": True,
        "label": label,
        "method": method,
        "members": list(members_data.keys()),
        "weights": {k: float(v) for k, v in weights.items()},
        "threshold": float(threshold) if threshold is not None else None,
        "features_union_size": len(features_union),
        "metrics": {k: float(v) if isinstance(v, (int, float)) else v
                    for k, v in metrics.items()},
    }
    meta_path = API_ARTIFACTS_DIR / "ensemble_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"   Metadata legacy del ensemble: {meta_path}")
else:
    # Ganador individual: un ensemble_meta.json de una exportacion anterior
    # describiria otro modelo -> se borra
    meta_path = API_ARTIFACTS_DIR / "ensemble_meta.json"
    if meta_path.exists():
        meta_path.unlink()
        print(f"   Borrado {meta_path.name} (de una exportacion anterior con ensemble)")

# ============================================================================
# RESUMEN
# ============================================================================
print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)

for artifact in sorted(API_ARTIFACTS_DIR.iterdir()):
    if artifact.name.startswith("."):
        continue
    size_kb = artifact.stat().st_size / 1024
    print(f"  {artifact.name} ({size_kb:.0f} KB)")

print(f"\nTipo: {'ENSEMBLE' if is_ensemble else f'INDIVIDUAL ({key})'}")
print(f"Total features: {len(feature_names)}")
print(f"  Numericas: {len(feature_names) - len(ohe_feats)}")
print(f"  OHE (cualitativas): {len(ohe_feats)}")
print("\nAPI lista para reiniciar: cd credit-scoring-api && uvicorn app.main:app --reload")
print("=" * 80)
