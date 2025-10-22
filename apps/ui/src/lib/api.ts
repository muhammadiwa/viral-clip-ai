const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export interface RequestOptions {
  method?: string
  body?: unknown
  token?: string | null
  orgId?: string | null
  signal?: AbortSignal
  idempotencyKey?: string
}

function resolveIdempotencyKey(key?: string) {
  if (key) return key
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return Math.random().toString(36).slice(2)
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `${API_BASE_URL.replace(/\/$/, '')}${path}`
  const headers = new Headers(options.body ? { 'Content-Type': 'application/json' } : undefined)
  headers.set('Accept', 'application/json')

  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`)
  }

  if (options.orgId) {
    headers.set('X-Org-ID', options.orgId)
  }

  if (options.body && (options.method ?? 'GET').toUpperCase() === 'POST') {
    headers.set('Idempotency-Key', resolveIdempotencyKey(options.idempotencyKey))
  }

  const response = await fetch(url, {
    method: options.method ?? 'GET',
    body: options.body ? JSON.stringify(options.body) : undefined,
    headers,
    signal: options.signal,
  })

  if (!response.ok) {
    let message = response.statusText || 'Request failed'
    let details: unknown
    try {
      const data = await response.json()
      if (data && typeof data.detail === 'string') {
        message = data.detail
      }
      details = data
    } catch (err) {
      // ignore json parse errors
    }
    throw new ApiError(message, response.status, details)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  if (!text) {
    return undefined as T
  }

  return JSON.parse(text) as T
}

export { API_BASE_URL }
