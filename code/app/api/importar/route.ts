/**
 * Proxy a FastAPI para importar el formulario de estados contables del BROU (FORM_BCE 2018).
 * Recibe el .xlsx tal cual (application/octet-stream) y devuelve los campos del formulario y los avisos.
 */

import { NextResponse } from "next/server"

const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000"

export async function POST(request: Request) {
  try {
    const archivo = await request.arrayBuffer()
    const response = await fetch(`${FASTAPI_URL}/importar/form-bce`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: archivo,
    })
    const data = await response.json().catch(() => ({ detail: response.statusText }))
    if (!response.ok) {
      return NextResponse.json({ error: data.detail || "No se pudo leer el formulario" }, { status: response.status })
    }
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con el API. Verificá que esté corriendo en http://localhost:8000" },
      { status: 500 },
    )
  }
}
