"""
Script simple para probar la API de Credit Scoring

Uso:
    1. Asegurar que la API está corriendo: uvicorn app.main:app --reload
    2. En otra terminal: python test_api_simple.py
"""

import requests
import json
from typing import Dict

# Configuración
API_URL = "http://localhost:8000"

def print_section(title: str):
    """Print section separator"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_health():
    """Test 1: Health check"""
    print_section("TEST 1: Health Check")
    
    response = requests.get(f"{API_URL}/health")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        print("✅ API está funcionando")
    else:
        print("❌ API no responde correctamente")
    
    return response.status_code == 200

def test_model_info():
    """Test 2: Model info"""
    print_section("TEST 2: Model Info")
    
    response = requests.get(f"{API_URL}/model/info")
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nModelo: {data['model_type']}")
        print(f"Features: {data['num_features']}")
        print(f"Performance:")
        print(f"  • AUC: {data['performance']['test_auc']}")
        print(f"  • KS: {data['performance']['test_ks']}")
        print("✅ Modelo cargado correctamente")
    else:
        print(f"❌ Error: {response.json()}")
    
    return response.status_code == 200

def test_predict_simple():
    """Test 3: Predicción simple"""
    print_section("TEST 3: Predicción Simple (Datos Mínimos)")
    
    payload = {
        "company_id": "test-001",
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
    
    print(f"Request:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{API_URL}/predict", json=payload)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ PREDICCIÓN EXITOSA:")
        print(f"  • Company ID: {result['company_id']}")
        print(f"  • Score: {result['score']}")
        print(f"  • Probabilidad: {result['probability']:.2%}")
        print(f"  • Rating: {result['risk_rating']['category']} - {result['risk_rating']['description']}")
        print(f"  • Color: {result['risk_rating']['color']}")
    else:
        print(f"❌ Error: {response.json()}")
    
    return response.status_code == 200

def test_predict_with_explanation():
    """Test 4: Predicción con explicación LIME"""
    print_section("TEST 4: Predicción con Explicación LIME")
    
    payload = {
        "company_id": "test-002",
        "features": {
            "TOTAL ACTIVO": 1000000,
            "TOTAL PASIVO": 800000,
            "TOTAL PATRIMONIO": 200000,
            "ROA": -0.05,  # ROA negativo = alto riesgo
            "Relacion_deuda_patrimonio": 4.0,  # Alto leverage
            "Capital": 50000
        },
        "explain": True  # Solicitar explicación
    }
    
    print(f"Request (empresa riesgosa):")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{API_URL}/predict", json=payload)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ PREDICCIÓN EXITOSA:")
        print(f"  • Score: {result['score']}")
        print(f"  • Probabilidad: {result['probability']:.2%}")
        print(f"  • Rating: {result['risk_rating']['category']}")
        
        if result.get('explanation'):
            print(f"\n📊 EXPLICACIÓN LIME (Top 5 factores):")
            for feat in result['explanation']['top_features'][:5]:
                contribution = feat['contribution']
                sign = "+" if contribution > 0 else ""
                emoji = "🔴" if contribution > 0 else "🟢"
                print(f"     {emoji} {feat['feature']}: {sign}{contribution:.4f}")
        else:
            print(f"\n⚠️  Explicación no disponible")
    else:
        print(f"❌ Error: {response.json()}")
    
    return response.status_code == 200

def test_predict_batch():
    """Test 5: Predicción batch"""
    print_section("TEST 5: Predicción Batch (3 empresas)")
    
    payload = {
        "companies": [
            {
                "TOTAL ACTIVO": 5000000,
                "TOTAL PASIVO": 2000000,
                "ROA": 0.15
            },
            {
                "TOTAL ACTIVO": 1000000,
                "TOTAL PASIVO": 900000,
                "ROA": -0.03
            },
            {
                "TOTAL ACTIVO": 3000000,
                "TOTAL PASIVO": 1500000,
                "ROA": 0.08
            }
        ],
        "explain": False
    }
    
    response = requests.post(f"{API_URL}/predict/batch", json=payload)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ BATCH PROCESADO:")
        print(f"  • Total: {result['total']}")
        print(f"  • Exitosos: {result['successful']}")
        print(f"  • Fallidos: {result['failed']}")
        
        print(f"\n  Resultados individuales:")
        for res in result['results']:
            if 'error' not in res:
                print(f"    [{res['index']}] Score: {res['score']}, "
                      f"Rating: {res['risk_rating']['category']}")
            else:
                print(f"    [{res['index']}] Error: {res['error']}")
    else:
        print(f"❌ Error: {response.json()}")
    
    return response.status_code == 200

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n🧪 INICIANDO TESTS DE API\n")
    print("⚠️  Asegúrate de que la API está corriendo en http://localhost:8000")
    print("   (uvicorn app.main:app --reload)\n")
    
    input("Presiona ENTER para continuar...")
    
    try:
        results = {
            "Health Check": test_health(),
            "Model Info": test_model_info(),
            "Predicción Simple": test_predict_simple(),
            "Predicción con LIME": test_predict_with_explanation(),
            "Predicción Batch": test_predict_batch()
        }
        
        # Resumen
        print("\n" + "="*80)
        print("RESUMEN DE TESTS")
        print("="*80)
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status}  {test_name}")
        
        total_passed = sum(results.values())
        total_tests = len(results)
        
        print(f"\n  Total: {total_passed}/{total_tests} tests pasaron")
        
        if total_passed == total_tests:
            print("\n🎉 TODOS LOS TESTS PASARON - API FUNCIONANDO CORRECTAMENTE")
        else:
            print("\n⚠️  Algunos tests fallaron - revisar logs de la API")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: No se pudo conectar a la API")
        print("   Asegúrate de que está corriendo:")
        print("   1. cd credit-scoring-api")
        print("   2. uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")

