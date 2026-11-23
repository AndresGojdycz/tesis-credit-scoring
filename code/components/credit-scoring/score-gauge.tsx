/**
 * Gauge visual para mostrar el score crediticio
 */

"use client"

import { cn } from "@/lib/utils"

interface ScoreGaugeProps {
  score: number
  /** Color de la banda del scorecard, tal como lo devuelve el API (risk_rating.color) */
  color: "green" | "yellow" | "orange" | "red"
  size?: "default" | "lg"
}

const COLOR_TEXTO = { green: "text-green-600", yellow: "text-yellow-500", orange: "text-orange-600", red: "text-red-600" }
const COLOR_TRAZO = { green: "stroke-green-600", yellow: "stroke-yellow-500", orange: "stroke-orange-600", red: "stroke-red-600" }

export function ScoreGauge({ score, color, size = "default" }: ScoreGaugeProps) {
  // Normalizar score a porcentaje sobre el rango teorico (0-1500 -> 0-100%)
  const normalized = Math.max(0, Math.min(100, (score / 1500) * 100))

  // El color sigue la banda que asigna el API con los cortes vigentes (model_card.json):
  // Bueno verde, Aceptable amarillo, Comprometido naranja, Critico rojo.
  const getColor = () => COLOR_TEXTO[color]
  const getGaugeColor = () => COLOR_TRAZO[color]

  const dimensions = size === "lg" ? { size: 200, stroke: 16 } : { size: 160, stroke: 12 }
  const { size: svgSize, stroke } = dimensions
  const radius = (svgSize - stroke) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (normalized / 100) * circumference

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className="relative">
        <svg width={svgSize} height={svgSize} className="-rotate-90">
          {/* Background circle */}
          <circle
            cx={svgSize / 2}
            cy={svgSize / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={stroke}
            fill="none"
            className="text-muted"
          />
          {/* Progress circle */}
          <circle
            cx={svgSize / 2}
            cy={svgSize / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={stroke}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={cn("transition-all duration-1000 ease-out", getGaugeColor())}
          />
        </svg>
        
        {/* Score in center */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <p className={cn("font-bold", size === "lg" ? "text-4xl" : "text-3xl", getColor())}>
            {score}
          </p>
          <p className="text-xs text-muted-foreground">Score</p>
        </div>
      </div>
      
      {/* Scale reference */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <div className="h-1 w-24 rounded-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500" />
      </div>
    </div>
  )
}

