import { NextResponse } from "next/server"

export async function POST(request: Request) {
  try {
    const body = await request.json()

    // Replace this URL with your actual FastAPI endpoint
    const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000/analyze"

    // Forward the request to FastAPI
    const response = await fetch(FASTAPI_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`FastAPI responded with status: ${response.status}`)
    }

    const data = await response.json()

    return NextResponse.json(data)
  } catch (error) {
    console.error("[v0] Error connecting to FastAPI:", error)

    // Return a mock response for demonstration
    // Remove this in production when FastAPI is connected
    return NextResponse.json({
      companyName: "Demo Response",
      score: 85,
      insights: [
        "Strong market presence in the specified industry",
        "Growth potential identified in emerging markets",
        "Competitive advantage through innovation",
        "Solid employee retention and satisfaction metrics",
      ],
      recommendations:
        "Consider expanding digital presence and investing in R&D to maintain competitive edge. Focus on sustainable growth strategies.",
      industry: "Technology",
      employees: 150,
    })
  }
}
