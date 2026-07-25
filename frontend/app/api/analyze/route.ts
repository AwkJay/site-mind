import { NextResponse } from 'next/server'
import OpenAI from 'openai'

// Create an OpenAI API client
const client = new OpenAI({
  apiKey: process.env.IAMHC_API_KEY || '',
  baseURL: process.env.IAMHC_BASE_URL || 'https://api.iamhc.cn/v1',
  maxRetries: 0, // Manual fallback
})

const FALLBACK_CHAIN = ['MiniMax-M3', 'DeepSeek-V4-Flash', 'Qwen3.6-35B-A3B']

export async function POST(req: Request) {
  try {
    const { text, analysisType } = await req.json()

    if (!text || !analysisType) {
      return NextResponse.json({ error: 'Missing text or analysisType' }, { status: 400 })
    }

    let systemPrompt = ''
    switch (analysisType) {
      case 'sentiment':
        systemPrompt = 'Analyze the sentiment of the following text. Respond with positive, negative, or neutral, followed by a brief explanation.'
        break
      case 'entity extraction':
        systemPrompt = 'Extract key entities (people, organizations, locations, dates, equipment, etc.) from the following text and list them.'
        break
      case 'classification':
        systemPrompt = 'Classify the following text into the most appropriate category for a construction/data-center project (e.g., Compliance, Safety, Schedule, Supply Chain, RFI, General).'
        break
      default:
        systemPrompt = 'Analyze the following text based on the provided instructions.'
    }

    let lastError: any = null

    // Fallback chain
    for (const model of FALLBACK_CHAIN) {
      try {
        const response = await client.chat.completions.create({
          model: model,
          stream: false,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: text }
          ],
        })
        
        return NextResponse.json({
          result: response.choices[0].message.content,
          model: model
        })
      } catch (error: any) {
        console.warn(`[analyze/route] Model ${model} failed:`, error?.message)
        lastError = error
        if (
          error instanceof OpenAI.RateLimitError ||
          error instanceof OpenAI.APIConnectionError ||
          error instanceof OpenAI.APIError
        ) {
          continue
        } else {
          continue
        }
      }
    }

    console.error('[analyze/route] All models in fallback chain failed.')
    return NextResponse.json({
      error: 'All models in the fallback chain failed.',
      details: lastError?.message
    }, { status: lastError?.status || 500 })

  } catch (error) {
    return NextResponse.json({ error: 'Failed to process request' }, { status: 500 })
  }
}
