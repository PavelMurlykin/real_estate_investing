import type { ZodType } from 'zod'

export class ApiError extends Error {
  readonly status: number

  readonly details: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

function getCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`
  const cookie = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))

  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null
}

async function readResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

export async function requestJson<ResponseType>(
  path: string,
  schema: ZodType<ResponseType>,
  options: RequestInit = {},
): Promise<ResponseType> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const method = (options.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    const csrfToken = getCookie('csrftoken')
    if (csrfToken) {
      headers.set('X-CSRFToken', csrfToken)
    }
  }

  const response = await fetch(path, {
    ...options,
    credentials: 'same-origin',
    headers,
  })
  const body = await readResponseBody(response)

  if (!response.ok) {
    throw new ApiError(
      'Сервер не смог выполнить запрос. Попробуйте ещё раз.',
      response.status,
      body,
    )
  }

  const parsedResponse = schema.safeParse(body)
  if (!parsedResponse.success) {
    throw new ApiError(
      'Сервер вернул данные в неожиданном формате.',
      response.status,
      parsedResponse.error,
    )
  }
  return parsedResponse.data
}

export async function requestWithoutResponse(
  path: string,
  options: RequestInit,
): Promise<void> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  const csrfToken = getCookie('csrftoken')
  if (csrfToken) {
    headers.set('X-CSRFToken', csrfToken)
  }

  const response = await fetch(path, {
    ...options,
    credentials: 'same-origin',
    headers,
  })
  if (!response.ok) {
    throw new ApiError(
      'Сервер не смог выполнить запрос. Попробуйте ещё раз.',
      response.status,
    )
  }
}
