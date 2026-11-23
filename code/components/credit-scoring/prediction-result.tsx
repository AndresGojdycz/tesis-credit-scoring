/**
 * Componente para mostrar resultados de la predicción
 */

"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { ScoreGauge } from "./score-gauge"
import type { PredictionResponse } from "@/lib/types"

interface PredictionResultProps {
  result: PredictionResponse
}

export function PredictionResult({ result }: PredictionResultProps) {
  const { score, risk_rating, company_id, prediction_timestamp, explanation, warnings } = result

  return (
    <div className="space-y-6">
      {/* Header con Company ID */}
      {company_id && (
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Empresa</p>
            <p className="text-lg font-semibold">{company_id}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Evaluado</p>
            <p className="text-sm">{new Date(prediction_timestamp).toLocaleString("es-CL")}</p>
          </div>
        </div>
      )}

      {/* Score Principal */}
      <Card>
        <CardHeader>
          <CardTitle className="text-center">Credit Score</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center">
          <ScoreGauge score={score} color={risk_rating.color} size="lg" />

          <div className="mt-6 w-full space-y-4">
            <Separator />

            {/* Clasificacion: banda y nivel de riesgo, como en la Tabla 6 de la tesis */}
            <div className="rounded-lg border-2 border-primary/20 bg-primary/5 p-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Clasificacion
                </p>
                <div className="text-right">
                  <span className="text-3xl font-bold text-primary">{risk_rating.category}</span>
                  <p className="text-sm text-muted-foreground">{risk_rating.description}</p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advertencias de calidad del input */}
      {warnings && warnings.length > 0 && (
        <Card className="border-yellow-300 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Advertencias sobre los datos ingresados</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Explicación LIME (si está disponible) */}
      {explanation && explanation.top_features && explanation.top_features.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Explicación del Modelo (LIME)</CardTitle>
            <CardDescription>
              Factores que más influyeron en esta decisión
            </CardDescription>
          </CardHeader>
          <CardContent>
            {explanation.summary && (
              <p className="mb-4 text-sm text-muted-foreground leading-relaxed">
                {explanation.summary}
              </p>
            )}
            <div className="space-y-3">
              {explanation.top_features.slice(0, 8).map((feat, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{feat.feature}</span>
                    <span className={feat.contribution > 0 ? "text-red-600" : "text-green-600"}>
                      {feat.contribution > 0 ? "+" : ""}
                      {feat.contribution.toFixed(4)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full ${
                        feat.contribution > 0 ? "bg-red-500" : "bg-green-500"
                      }`}
                      style={{
                        width: `${Math.min(100, Math.abs(feat.contribution) * 200)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            
            <div className="mt-4 rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              <p>
                🔴 <strong>Positivo</strong> = Aumenta riesgo de default
              </p>
              <p>
                🟢 <strong>Negativo</strong> = Disminuye riesgo de default
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

