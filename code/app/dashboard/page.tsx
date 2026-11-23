/**
 * Dashboard Principal de Credit Scoring
 */

"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  TrendingUp,
  Loader2,
  Download,
} from "lucide-react"
import { CompanyForm } from "@/components/credit-scoring/company-form"
import { PredictionResult } from "@/components/credit-scoring/prediction-result"
import type { CompanyFeatures, PredictionResponse } from "@/lib/types"

export default function DashboardPage() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PredictionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [apiStatus, setApiStatus] = useState<"checking" | "connected" | "disconnected">("checking")
  const [history, setHistory] = useState<PredictionResponse[]>([])

  // Verificar conexión con FastAPI al cargar
  useEffect(() => {
    checkAPIConnection()
  }, [])

  const checkAPIConnection = async () => {
    setApiStatus("checking")
    try {
      const response = await fetch("/api/predict")
      const data = await response.json()
      
      if (data.fastapi_connected) {
        setApiStatus("connected")
      } else {
        setApiStatus("disconnected")
      }
    } catch (error) {
      setApiStatus("disconnected")
    }
  }

  const handleSubmit = async (features: CompanyFeatures, companyId?: string) => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch("/api/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          company_id: companyId,
          features,
          explain: true, // Siempre pedir explicación
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || errorData.detail || "Error en la predicción")
      }

      const data: PredictionResponse = await response.json()
      setResult(data)
      
      // Agregar al historial
      setHistory(prev => [data, ...prev.slice(0, 9)]) // Máximo 10 en historial
      
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido")
    } finally {
      setLoading(false)
    }
  }

  const downloadResults = () => {
    if (!result) return
    
    const dataStr = JSON.stringify(result, null, 2)
    const dataBlob = new Blob([dataStr], { type: "application/json" })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement("a")
    link.href = url
    link.download = `credit-score-${result.company_id || Date.now()}.json`
    link.click()
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
                Credit Scoring Dashboard
              </h1>
              <p className="mt-2 text-muted-foreground">
                Sistema de evaluación crediticia empresarial con Machine Learning
              </p>
            </div>
            
            {/* API Status Badge */}
            <div className="flex items-center gap-2">
              {apiStatus === "checking" && (
                <Badge variant="outline" className="gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Verificando...
                </Badge>
              )}
              {apiStatus === "connected" && (
                <Badge variant="default" className="gap-2 bg-green-600">
                  <CheckCircle2 className="h-3 w-3" />
                  API Conectada
                </Badge>
              )}
              {apiStatus === "disconnected" && (
                <Badge variant="destructive" className="gap-2">
                  <AlertCircle className="h-3 w-3" />
                  API Desconectada
                </Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={checkAPIConnection}
              >
                Reconectar
              </Button>
            </div>
          </div>
        </div>

        {/* API Disconnected Warning */}
        {apiStatus === "disconnected" && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <p className="font-semibold">FastAPI no está conectada</p>
              <p className="mt-1 text-sm">
                Asegúrate de que la API esté corriendo:
                <code className="ml-2 rounded bg-background px-2 py-1">
                  uvicorn app.main:app --reload
                </code>
              </p>
            </AlertDescription>
          </Alert>
        )}

        {/* Main Content */}
        <Tabs defaultValue="evaluate" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="evaluate">
              <TrendingUp className="mr-2 h-4 w-4" />
              Evaluar Empresa
            </TabsTrigger>
            <TabsTrigger value="history">
              <Clock className="mr-2 h-4 w-4" />
              Historial ({history.length})
            </TabsTrigger>
          </TabsList>

          {/* Tab: Evaluar Empresa */}
          <TabsContent value="evaluate" className="mt-6">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Formulario */}
              <div>
                <CompanyForm onSubmit={handleSubmit} loading={loading} />
              </div>

              {/* Resultados */}
              <div>
                {loading && (
                  <Card>
                    <CardContent className="flex min-h-[400px] items-center justify-center py-12">
                      <div className="text-center">
                        <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
                        <p className="font-medium">Analizando empresa...</p>
                        <p className="mt-2 text-sm text-muted-foreground">
                          Procesando con el modelo (Random Forest)
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {error && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      <p className="font-semibold">Error</p>
                      <p className="mt-1 text-sm">{error}</p>
                    </AlertDescription>
                  </Alert>
                )}

                {result && !loading && (
                  <div className="space-y-4">
                    <h2 className="text-lg font-semibold">Resultados</h2>
                    <PredictionResult result={result} />
                  </div>
                )}

                {!loading && !error && !result && (
                  <Card className="border-dashed">
                    <CardContent className="flex min-h-[400px] items-center justify-center py-12">
                      <div className="text-center">
                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                          <TrendingUp className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Completa el formulario para evaluar una empresa
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </TabsContent>

          {/* Tab: Historial */}
          <TabsContent value="history" className="mt-6">
            {history.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="flex min-h-[300px] items-center justify-center py-12">
                  <div className="text-center">
                    <Clock className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      No hay evaluaciones previas en esta sesión
                    </p>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {history.map((item, idx) => (
                  <Card
                    key={idx}
                    className="cursor-pointer transition-shadow hover:shadow-md"
                    onClick={() => setResult(item)}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">
                          {item.company_id || `Evaluación #${idx + 1}`}
                        </CardTitle>
                        <Badge
                          variant="outline"
                          className={
                            item.risk_rating.color === "green"
                              ? "border-green-600 text-green-600"
                              : item.risk_rating.color === "yellow"
                              ? "border-yellow-600 text-yellow-600"
                              : item.risk_rating.color === "orange"
                              ? "border-orange-600 text-orange-600"
                              : "border-red-600 text-red-600"
                          }
                        >
                          {item.risk_rating.category}
                        </Badge>
                      </div>
                      <CardDescription className="text-xs">
                        {new Date(item.prediction_timestamp).toLocaleString("es-CL")}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Score</p>
                          <p className="text-xl font-bold">{item.score}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Riesgo</p>
                          <p className="text-xl font-bold">{(item.probability * 100).toFixed(1)}%</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

        </Tabs>
      </div>
    </div>
  )
}

