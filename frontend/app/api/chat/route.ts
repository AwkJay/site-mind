import OpenAI from 'openai'

// Create an OpenAI API client
const client = new OpenAI({
  apiKey: process.env.IAMHC_API_KEY || '',
  baseURL: process.env.IAMHC_BASE_URL || 'https://api.iamhc.cn/v1',
  maxRetries: 0, // We handle retries/fallbacks manually
})

const FALLBACK_CHAIN = ['MiniMax-M3', 'DeepSeek-V4-Flash', 'Qwen3.6-35B-A3B']

export async function POST(req: Request) {
  const { messages } = await req.json()
  let lastError: any = null

  // Fallback chain
  for (const model of FALLBACK_CHAIN) {
    try {
      const response = await client.chat.completions.create({
        model: model,
        stream: true,
        messages: messages,
      })

      const stream = new ReadableStream({
        async start(controller) {
          try {
            for await (const chunk of response) {
              const content = chunk.choices[0]?.delta?.content || ''
              if (content) {
                controller.enqueue(new TextEncoder().encode(content))
              }
            }
          } catch (err) {
            controller.error(err)
          } finally {
            controller.close()
          }
        },
      })
      
      return new Response(stream, {
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      })
    } catch (error: any) {
      console.warn(`[chat/route] Model ${model} failed:`, error?.message)
      lastError = error
      if (
        error instanceof OpenAI.RateLimitError ||
        error instanceof OpenAI.APIConnectionError ||
        error instanceof OpenAI.APIError
      ) {
        continue // Try the next model
      } else {
        continue
      }
    }
  }

  console.error('[chat/route] All models in fallback chain failed.')
  
  return new Response(JSON.stringify({
    error: 'All models in the fallback chain failed.',
    details: lastError?.message
  }), {
    status: lastError?.status || 500,
    headers: { 'Content-Type': 'application/json' }
  })
}

