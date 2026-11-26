import { request } from './client'

export type QualityJson = Record<string, any>

async function parse<T = QualityJson>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message =
      (data as QualityJson)?.detail ||
      (data as QualityJson)?.message ||
      `接口返回 ${response.status}`
    throw new Error(String(message))
  }
  return data as T
}

export async function qualityGet<T = QualityJson>(path: string): Promise<T> {
  return parse<T>(await request(path))
}

export async function qualityPost<T = QualityJson>(
  path: string,
  body: QualityJson = {},
): Promise<T> {
  return parse<T>(
    await request(path, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  )
}

export function queryString(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}
