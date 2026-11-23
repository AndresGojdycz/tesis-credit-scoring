/**
 * API Route que actúa como proxy a la FastAPI de Credit Scoring
 * 
 * Por qué necesitamos esto:
 * - Next.js (frontend) corre en el navegador
 * - FastAPI corre en localhost:8000 (backend)
 * - CORS puede causar problemas
 * - Esta ruta evita CORS al hacer la llamada server-side
 */

import { NextResponse } from "next/server"
import type { PredictionRequest, PredictionResponse } from "@/lib/types"

// URL de tu FastAPI - configurable via env variable
const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000"

export async function POST(request: Request) {
  try {
    const body: PredictionRequest = await request.json()

    console.log("[API Route] Forwarding request to FastAPI...")
    console.log(`[API Route] Features received:`, Object.keys(body.features || {}).length)

    // Llamar a FastAPI
    const response = await fetch(`${FASTAPI_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }))
      console.error("[API Route] FastAPI error:", errorData)
      
      return NextResponse.json(
        { error: errorData.detail || "Error en predicción" },
        { status: response.status }
      )
    }

    const data: PredictionResponse = await response.json()
    
    console.log("[API Route] Success! Score:", data.score, "Rating:", data.risk_rating.category)

    return NextResponse.json(data)
    
  } catch (error) {
    console.error("[API Route] Error:", error)

    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Error desconocido",
        detail: "No se pudo conectar con FastAPI. Asegúrate de que esté corriendo en http://localhost:8000",
      },
      { status: 500 }
    )
  }
}

/**
 * GET endpoint para verificar estado
 */
export async function GET() {
  try {
    const healthResponse = await fetch(`${FASTAPI_URL}/health`)
    const healthData = await healthResponse.json()

    return NextResponse.json({
      status: "ok",
      fastapi_connected: healthResponse.ok,
      fastapi_health: healthData,
    })
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        fastapi_connected: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 503 }
    )
  }
}

