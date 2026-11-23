#!/bin/bash

# Credit Scoring API - Start Script

echo "=========================================="
echo "  Credit Scoring API - Startup"
echo "=========================================="

# Check if artifacts exist
if [ ! -f "artifacts/model.pkl" ]; then
    echo ""
    echo "⚠️  WARNING: Modelo no encontrado en artifacts/"
    echo ""
    echo "Por favor ejecuta primero:"
    echo "  python ../export_artifacts_for_api.py"
    echo ""
    exit 1
fi

echo ""
echo "✅ Artifacts encontrados"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creando virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activando virtual environment..."
source .venv/bin/activate

# Install dependencies
echo ""
echo "Instalando dependencias..."
pip install -r requirements.txt --quiet

# Start API
echo ""
echo "=========================================="
echo "  Iniciando API en http://localhost:8000"
echo "=========================================="
echo ""
echo "Documentación: http://localhost:8000/docs"
echo "Health Check:  http://localhost:8000/health"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

