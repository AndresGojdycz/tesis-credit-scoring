/**
 * Types para Credit Scoring API
 * Basado en los schemas de Pydantic de FastAPI
 */

export interface CompanyFeatures {
  // Balance Sheet - Activos
  "TOTAL ACTIVO"?: number
  "Activo Circulante"?: number
  Disponible?: number
  "Depósitos a Plazo"?: number
  "Valores Negociables"?: number
  "Documentos por Recibir"?: number
  Existencias?: number
  "Activo Fijo"?: number
  Intangibles?: number
  
  // Balance Sheet - Pasivos  
  "TOTAL PASIVO"?: number
  "Pasivo Circulante"?: number
  "Obligaciones con Bancos e Instituciones Financieras C.P."?: number
  "Pasivo Largo Plazo"?: number
  
  // Balance Sheet - Patrimonio
  "TOTAL PATRIMONIO"?: number
  "Capital Pagado"?: number
  "Utilidades Retenidas de Ejercicios Anteriores"?: number
  
  // P&L
  "Resultado Operacional"?: number
  "Resultado No Operacional"?: number
  "RESULTADO NETO DEL EJERCICIO (UTILIDAD o PÉRDIDA)"?: number
  "Ventas Plaza"?: number
  "Ventas al Extranjero"?: number
  "Ingresos de Explotación"?: number
  "Costo de Explotación"?: number
  "Gastos de Administración y Ventas"?: number
  "Depreciación del Ejercicio"?: number
  "Ingresos Financieros"?: number
  "Intereses y Gastos Financieros"?: number
  
  // Ratios Calculados
  ROA?: number
  ROE?: number
  Relacion_deuda_patrimonio?: number
  Capital?: number
  Cobertura_intereses?: number
  
  // Otros
  Bancos?: number
  Documentos?: number
  "Capital Propio"?: number
  Multiplicador?: number
  
  // Variables cualitativas
  TIPO_SOCIEDAD?: string
  ACTIVIDAD_ECONOMICA?: string
  TAMANO_EMPRESA?: string

  // Permite cualquier otra feature
  [key: string]: number | string | undefined
}

export interface RiskRating {
  category: "Bueno" | "Aceptable" | "Comprometido" | "Crítico"
  description: string
  color: "green" | "yellow" | "orange" | "red"
}

export interface LIMEExplanation {
  top_features: Array<{
    feature: string
    contribution: number
  }>
  prediction?: number
  intercept?: number
  summary?: string
}

export interface PredictionRequest {
  company_id?: string
  features: CompanyFeatures
  explain?: boolean
}

export interface PredictionResponse {
  company_id?: string
  probability: number
  score: number
  risk_rating: RiskRating
  prediction_timestamp: string
  model_version: string
  explanation?: LIMEExplanation | null
  warnings?: string[] | null
}

export interface BatchPredictionRequest {
  companies: CompanyFeatures[]
  explain?: boolean
}

export interface BatchPredictionResponse {
  total: number
  successful: number
  failed: number
  results: Array<{
    index: number
    probability?: number
    score?: number
    risk_rating?: RiskRating
    error?: string
  }>
}

export interface ModelInfo {
  model_type: string
  model_version: string
  num_features: number
  features: string[]
  target: string
  performance: {
    test_auc: number
    test_ks: number
    overfit_gap: number
  }
  training_date: string
  training_samples: number
}

export interface HealthResponse {
  status: "healthy" | "unhealthy"
  model_loaded: boolean
  model_version: string
  uptime_seconds: number
}

