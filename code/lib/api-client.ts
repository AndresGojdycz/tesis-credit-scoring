/**
 * Cliente para conectar con la Credit Scoring API (FastAPI)
 */

import type {
  PredictionRequest,
  PredictionResponse,
  BatchPredictionRequest,
  BatchPredictionResponse,
  ModelInfo,
  HealthResponse,
} from "./types"

// URL de la API - puede ser configurada via env variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

/**
 * Cliente de la Credit Scoring API
 */
export class CreditScoringAPI {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  /**
   * Health check
   */
  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`)
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`)
    }
    
    return response.json()
  }

  /**
   * Información del modelo
   */
  async modelInfo(): Promise<ModelInfo> {
    const response = await fetch(`${this.baseUrl}/model/info`)
    
    if (!response.ok) {
      throw new Error(`Failed to get model info: ${response.statusText}`)
    }
    
    return response.json()
  }

  /**
   * Predicción individual
   */
  async predict(request: PredictionRequest): Promise<PredictionResponse> {
    const response = await fetch(`${this.baseUrl}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || "Prediction failed")
    }

    return response.json()
  }

  /**
   * Predicción batch
   */
  async predictBatch(request: BatchPredictionRequest): Promise<BatchPredictionResponse> {
    const response = await fetch(`${this.baseUrl}/predict/batch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || "Batch prediction failed")
    }

    return response.json()
  }
}

// Singleton instance
export const apiClient = new CreditScoringAPI()

/**
 * React hooks para usar en componentes
 */

export async function checkAPIHealth() {
  try {
    const health = await apiClient.health()
    return { connected: health.model_loaded, ...health }
  } catch (error) {
    return { connected: false, error: error instanceof Error ? error.message : "Unknown error" }
  }
}

