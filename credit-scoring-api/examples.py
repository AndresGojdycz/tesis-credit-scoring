"""
Ejemplos de uso de la Credit Scoring API

Ejecutar la API primero:
    uvicorn app.main:app --reload

Luego ejecutar este script:
    python examples.py
"""

import requests
import json

API_URL = "http://localhost:8000"


def ejemplo_1_empresa_sana():
    """Ejemplo 1: Empresa sana con buenos indicadores"""
    print("\n" + "="*80)
    print("EJEMPLO 1: EMPRESA SANA (Buenos indicadores financieros)")
    print("="*80)
    
    payload = {
        "company_id": "EMP-001",
        "features": {
            "TOTAL ACTIVO": 10000000,
            "TOTAL PASIVO": 4000000,
            "TOTAL PATRIMONIO": 6000000,
            "ROA": 0.18,  # Excelente rentabilidad
            "ROE": 0.25,  # Excelente retorno
            "Relacion_deuda_patrimonio": 0.67,  # Bajo apalancamiento
            "Capital": 2000000,  # Capital positivo
            "Resultado Operacional": 1800000,
            "Ventas Plaza": 15000000,
            "Bancos": 500000
        },
        "explain": True
    }
    
    response = requests.post(f"{API_URL}/predict", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ RESULTADO:")
        print(f"   Company ID: {result['company_id']}")
        print(f"   Score: {result['score']}")
        print(f"   Probabilidad de default: {result['probability']:.2%}")
        print(f"   Rating: {result['risk_rating']['category']} - {result['risk_rating']['description']}")
        
        if result.get('explanation'):
            print(f"\n📊 Top factores (LIME):")
            for feat in result['explanation']['top_features'][:5]:
                sign = "+" if feat['contribution'] > 0 else ""
                emoji = "🔴" if feat['contribution'] > 0 else "🟢"
                print(f"      {emoji} {feat['feature']}: {sign}{feat['contribution']:.4f}")
        
        # Decisión
        if result['score'] >= 650:
            print(f"\n💼 DECISIÓN: ✅ APROBAR préstamo con condiciones estándar")
        elif result['score'] >= 500:
            print(f"\n💼 DECISIÓN: ⚠️  APROBAR con garantías adicionales")
        else:
            print(f"\n💼 DECISIÓN: ❌ RECHAZAR préstamo")
    else:
        print(f"❌ Error: {response.json()}")


def ejemplo_2_empresa_riesgosa():
    """Ejemplo 2: Empresa riesgosa"""
    print("\n" + "="*80)
    print("EJEMPLO 2: EMPRESA RIESGOSA (Indicadores débiles)")
    print("="*80)
    
    payload = {
        "company_id": "EMP-002",
        "features": {
            "TOTAL ACTIVO": 1000000,
            "TOTAL PASIVO": 950000,
            "TOTAL PATRIMONIO": 50000,  # Muy poco patrimonio
            "ROA": -0.08,  # Pérdidas operacionales
            "ROE": -0.45,  # Retorno negativo
            "Relacion_deuda_patrimonio": 19.0,  # Extremadamente apalancada
            "Capital": -100000,  # Capital de trabajo negativo
            "Resultado Operacional": -80000,
            "Ventas Plaza": 500000,
            "Bancos": 10000
        },
        "explain": True
    }
    
    response = requests.post(f"{API_URL}/predict", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ RESULTADO:")
        print(f"   Company ID: {result['company_id']}")
        print(f"   Score: {result['score']}")
        print(f"   Probabilidad de default: {result['probability']:.2%}")
        print(f"   Rating: {result['risk_rating']['category']} - {result['risk_rating']['description']}")
        
        if result.get('explanation'):
            print(f"\n📊 Factores de RIESGO (LIME):")
            for feat in result['explanation']['top_features'][:5]:
                sign = "+" if feat['contribution'] > 0 else ""
                emoji = "🔴" if feat['contribution'] > 0 else "🟢"
                print(f"      {emoji} {feat['feature']}: {sign}{feat['contribution']:.4f}")
        
        # Decisión
        if result['score'] >= 650:
            print(f"\n💼 DECISIÓN: ✅ APROBAR")
        elif result['score'] >= 500:
            print(f"\n💼 DECISIÓN: ⚠️  APROBAR con condiciones")
        else:
            print(f"\n💼 DECISIÓN: ❌ RECHAZAR - Alto riesgo")
    else:
        print(f"❌ Error: {response.json()}")


def ejemplo_3_datos_parciales():
    """Ejemplo 3: Datos incompletos (muy común en realidad)"""
    print("\n" + "="*80)
    print("EJEMPLO 3: DATOS PARCIALES (Missing values)")
    print("="*80)
    
    payload = {
        "company_id": "EMP-003",
        "features": {
            "TOTAL ACTIVO": 3000000,
            # TOTAL PASIVO faltante - será imputado
            # TOTAL PATRIMONIO faltante - será imputado
            "ROA": 0.10,
            # ROE faltante
            "Capital": 300000,
            "Ventas Plaza": 5000000
            # Solo 4 features de 82!
        },
        "explain": False
    }
    
    print(f"\n📝 Request con solo 4 features:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{API_URL}/predict", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ MODELO MANEJA MISSING VALUES:")
        print(f"   Score: {result['score']}")
        print(f"   Rating: {result['risk_rating']['category']}")
        print(f"   Probabilidad: {result['probability']:.2%}")
        print(f"\n💡 SimpleImputer rellenó features faltantes automáticamente")
    else:
        print(f"❌ Error: {response.json()}")


def ejemplo_4_batch():
    """Ejemplo 4: Predicción batch de múltiples empresas"""
    print("\n" + "="*80)
    print("EJEMPLO 4: PREDICCIÓN BATCH (3 empresas simultáneas)")
    print("="*80)
    
    payload = {
        "companies": [
            {
                "TOTAL ACTIVO": 8000000,
                "TOTAL PASIVO": 3000000,
                "ROA": 0.20,
                "Capital": 1500000
            },
            {
                "TOTAL ACTIVO": 2000000,
                "TOTAL PASIVO": 1900000,
                "ROA": -0.05,
                "Capital": -50000
            },
            {
                "TOTAL ACTIVO": 5000000,
                "TOTAL PASIVO": 2500000,
                "ROA": 0.12,
                "Capital": 800000
            }
        ],
        "explain": False
    }
    
    response = requests.post(f"{API_URL}/predict/batch", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ BATCH PROCESADO:")
        print(f"   Total: {result['total']}")
        print(f"   Exitosos: {result['successful']}")
        
        print(f"\n   Resultados:")
        for res in result['results']:
            idx = res['index']
            if 'error' not in res:
                print(f"      [{idx}] Score: {res['score']:>4} | "
                      f"Rating: {res['risk_rating']['category']:>3} | "
                      f"Prob: {res['probability']:>5.2%}")
            else:
                print(f"      [{idx}] Error: {res['error']}")
    else:
        print(f"❌ Error: {response.json()}")


def ejemplo_5_integracion_sistema():
    """Ejemplo 5: Integración con sistema de decisión"""
    print("\n" + "="*80)
    print("EJEMPLO 5: INTEGRACIÓN CON SISTEMA DE DECISIÓN AUTOMÁTICA")
    print("="*80)
    
    # Simular múltiples solicitudes de crédito
    solicitudes = [
        {"id": "SOL-001", "monto": 500000, "roa": 0.18, "activo": 10000000},
        {"id": "SOL-002", "monto": 200000, "roa": 0.05, "activo": 2000000},
        {"id": "SOL-003", "monto": 1000000, "roa": -0.03, "activo": 1500000},
    ]
    
    print(f"\nProcesando {len(solicitudes)} solicitudes de crédito...\n")
    
    decisiones = []
    
    for sol in solicitudes:
        # Llamar a la API
        payload = {
            "company_id": sol['id'],
            "features": {
                "TOTAL ACTIVO": sol['activo'],
                "ROA": sol['roa'],
                "Capital": sol['activo'] * 0.1  # 10% del activo
            },
            "explain": False
        }
        
        response = requests.post(f"{API_URL}/predict", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            score = result['score']
            prob = result['probability']
            
            # Lógica de decisión automática
            if score >= 700:
                decision = "APROBADO - Tasa preferencial"
                tasa = 5.0
            elif score >= 600:
                decision = "APROBADO - Tasa estándar"
                tasa = 8.0
            elif score >= 500:
                decision = "APROBADO CON CONDICIONES - Tasa alta + garantías"
                tasa = 12.0
            else:
                decision = "RECHAZADO - Alto riesgo"
                tasa = None
            
            decisiones.append({
                "solicitud": sol['id'],
                "monto": sol['monto'],
                "score": score,
                "probabilidad": prob,
                "decision": decision,
                "tasa": tasa
            })
            
            print(f"[{sol['id']}]")
            print(f"  Monto: ${sol['monto']:,}")
            print(f"  Score: {score}")
            print(f"  Probabilidad default: {prob:.2%}")
            print(f"  Decisión: {decision}")
            if tasa:
                print(f"  Tasa ofrecida: {tasa}%")
            print()
    
    # Resumen
    print("\n" + "-"*80)
    print("RESUMEN DE DECISIONES")
    print("-"*80)
    aprobados = sum(1 for d in decisiones if "APROBADO" in d['decision'])
    rechazados = len(decisiones) - aprobados
    print(f"  Aprobados: {aprobados}")
    print(f"  Rechazados: {rechazados}")
    print(f"  Total procesado: ${sum(d['monto'] for d in decisiones):,}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n🧪 EJEMPLOS DE USO - CREDIT SCORING API\n")
    
    try:
        # Health check
        response = requests.get(f"{API_URL}/health")
        if response.status_code != 200:
            print("❌ API no está corriendo")
            print("   Ejecuta primero: uvicorn app.main:app --reload")
            exit(1)
        
        print("✅ API está corriendo\n")
        
        # Ejecutar ejemplos
        ejemplo_1_empresa_sana()
        ejemplo_2_empresa_riesgosa()
        ejemplo_3_datos_parciales()
        ejemplo_4_batch()
        ejemplo_5_integracion_sistema()
        
        print("\n" + "="*80)
        print("✅ TODOS LOS EJEMPLOS EJECUTADOS")
        print("="*80)
        print("\nPróximos pasos:")
        print("  • Explorar documentación interactiva: http://localhost:8000/docs")
        print("  • Integrar con tu sistema")
        print("  • Deploy en producción")
        
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar a la API")
        print("   Asegúrate de que está corriendo:")
        print("   uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")

