"use client"

import { useRouter } from "next/navigation"
import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ArrowRight, Zap } from "lucide-react"

export default function HomePage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      <div className="container mx-auto px-4 py-16">
        {/* Hero Section */}
        <div className="mb-16 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2 text-sm font-medium text-primary">
            <Zap className="h-4 w-4" />
            Powered by Machine Learning
          </div>
          
          <h1 className="mb-4 text-4xl font-bold tracking-tight md:text-6xl">
            Credit Scoring
            <span className="bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
              {" "}Empresarial
            </span>
          </h1>
          
          <p className="mx-auto mb-8 max-w-2xl text-lg text-muted-foreground">
            Sistema de evaluación crediticia con Machine Learning que predice el riesgo de default
            en los 12 meses siguientes al cierre del balance, con un AUC de 0,751 en test.
          </p>

          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" onClick={() => router.push("/dashboard")}>
              Ir al Dashboard
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" asChild>
              <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">
                Ver API Docs
              </a>
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div>
          <h2 className="mb-8 text-center text-2xl font-bold">Métricas del Modelo</h2>
          <div className="grid gap-6 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold text-primary">0,751</p>
                <p className="text-sm text-muted-foreground">Test AUC</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold text-primary">0,449</p>
                <p className="text-sm text-muted-foreground">KS Statistic</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold text-primary">0,688</p>
                <p className="text-sm text-muted-foreground">CV AUC (media 5 folds)</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold text-primary">107</p>
                <p className="text-sm text-muted-foreground">Features</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
