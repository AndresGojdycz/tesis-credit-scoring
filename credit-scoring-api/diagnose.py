"""
Script de diagnóstico para la API

Ejecutar:
    python3 diagnose.py
"""

import sys
from pathlib import Path

print("="*80)
print("DIAGNÓSTICO DE LA API")
print("="*80)

# 1. Verificar archivos críticos
print("\n1. Verificando archivos...")

files_to_check = [
    "app/__init__.py",
    "app/main.py",
    "app/models.py",
    "app/config.py",
    "app/predictor.py",
    "app/explainer.py",
    "artifacts/rf_model_calibrated_raw_future.pkl",
    "artifacts/feature_names.pkl",
]

for file_path in files_to_check:
    p = Path(file_path)
    if p.exists():
        size = p.stat().st_size
        print(f"   ✅ {file_path} ({size:,} bytes)")
    else:
        print(f"   ❌ {file_path} NO EXISTE")

# 2. Probar imports
print("\n2. Probando imports...")

try:
    print("   Importando app.config...")
    from app.config import settings
    print(f"   ✅ app.config OK")
    print(f"      MODEL_PATH: {settings.MODEL_PATH}")
    print(f"      Existe: {settings.MODEL_PATH.exists()}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

try:
    print("   Importando app.models...")
    from app.models import CompanyFeatures, PredictionRequest, PredictionResponse
    print(f"   ✅ app.models OK")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

try:
    print("   Importando app.predictor...")
    from app.predictor import predictor
    print(f"   ✅ app.predictor OK")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

try:
    print("   Importando app.explainer...")
    from app.explainer import lime_explainer
    print(f"   ✅ app.explainer OK")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

try:
    print("   Importando app.main...")
    from app.main import app
    print(f"   ✅ app.main OK")
    print(f"      App type: {type(app)}")
except Exception as e:
    print(f"   ❌ Error importando app.main: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Probar carga del modelo
print("\n3. Probando carga del modelo...")

try:
    print("   Cargando modelo...")
    predictor.load_model()
    print(f"   ✅ Modelo cargado")
    print(f"      Features: {len(predictor.feature_names)}")
    print(f"      Top 5: {predictor.feature_names[:5]}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# 4. Test de predicción
print("\n4. Probando predicción...")

try:
    test_features = CompanyFeatures(**{
        "TOTAL ACTIVO": 5000000,
        "TOTAL PASIVO": 3000000,
        "ROA": 0.15
    })
    
    result = predictor.predict(test_features)
    print(f"   ✅ Predicción exitosa")
    print(f"      Score: {result['score']}")
    print(f"      Probability: {result['probability']:.4f}")
    print(f"      Rating: {result['risk_rating'].category}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("DIAGNÓSTICO COMPLETO")
print("="*80)
print("\nSi todos los checks pasaron, la API debería funcionar con:")
print("  uvicorn app.main:app --reload")
print("="*80)

