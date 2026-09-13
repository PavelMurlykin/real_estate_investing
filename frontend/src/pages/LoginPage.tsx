import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useState } from 'react'
import {
  Link,
  Navigate,
  useNavigate,
  useSearchParams,
} from 'react-router-dom'

import { ApiError } from '@/api/client'
import { loginUser, sessionQueryOptions } from '@/api/queries'
import type { Session } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type SafeNextPath = {
  browserPath: string
  routerPath: string
}

function safeNextPath(requestedPath: string | null): SafeNextPath {
  const fallback = { browserPath: '/app/', routerPath: '/' }
  if (!requestedPath) return fallback

  try {
    const requestedUrl = new URL(requestedPath, window.location.origin)
    if (requestedUrl.origin !== window.location.origin) return fallback
    if (
      requestedUrl.pathname !== '/app'
      && !requestedUrl.pathname.startsWith('/app/')
    ) {
      return fallback
    }

    const applicationPath = requestedUrl.pathname === '/app'
      ? '/app/'
      : requestedUrl.pathname
    const routerPath = applicationPath.slice('/app'.length) || '/'
    if (routerPath === '/login' || routerPath.startsWith('/login/')) {
      return fallback
    }
    const suffix = `${requestedUrl.search}${requestedUrl.hash}`
    return {
      browserPath: `${applicationPath}${suffix}`,
      routerPath: `${routerPath}${suffix}`,
    }
  } catch {
    return fallback
  }
}

function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstMessage(item)
      if (message) return message
    }
  }
  return null
}

function loginErrorMessage(error: unknown): string {
  if (
    error instanceof ApiError
    && error.details
    && typeof error.details === 'object'
    && !Array.isArray(error.details)
  ) {
    const details = error.details as Record<string, unknown>
    const nestedErrors = (
      details.errors
      && typeof details.errors === 'object'
      && !Array.isArray(details.errors)
    )
      ? details.errors as Record<string, unknown>
      : {}
    return firstMessage(nestedErrors.nonFieldErrors)
      ?? firstMessage(details.identifier)
      ?? firstMessage(details.password)
      ?? error.message
  }
  return 'Не удалось войти. Повторите попытку.'
}

export function LoginPage() {
  useDocumentTitle('Вход')
  const [searchParameters] = useSearchParams()
  const [clientError, setClientError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const sessionQuery = useQuery(sessionQueryOptions)
  const nextPath = safeNextPath(searchParameters.get('next'))
  const loginMutation = useMutation({
    mutationFn: loginUser,
    onSuccess: (session: Session) => {
      queryClient.setQueryData(['session'], session)
      navigate(nextPath.routerPath, { replace: true })
    },
  })

  const submitLogin = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    loginMutation.reset()
    setClientError(null)
    const formData = new FormData(event.currentTarget)
    const identifier = String(formData.get('identifier') ?? '').trim()
    const password = String(formData.get('password') ?? '')
    if (!identifier || !password) {
      setClientError('Введите email или телефон и пароль.')
      return
    }
    loginMutation.mutate({ identifier, password })
  }

  if (sessionQuery.isLoading) return <PageLoadingState />
  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }
  if (sessionQuery.data?.isAuthenticated) {
    return <Navigate replace to={nextPath.routerPath} />
  }

  const errorMessage = clientError
    ?? (loginMutation.isError ? loginErrorMessage(loginMutation.error) : null)
  const legacyLoginUrl = (
    `/users/login/?next=${encodeURIComponent(nextPath.browserPath)}`
  )

  return (
    <div className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <header className="auth-card__header">
          <span className="eyebrow">Личный кабинет</span>
          <h1 id="login-title">Вход</h1>
          <p>
            Войдите по электронной почте или телефону, чтобы работать с
            клиентами и сохранёнными расчётами.
          </p>
        </header>

        {searchParameters.get('registered') === '1' ? (
          <p className="account-form-status" role="status">
            Аккаунт создан. Теперь войдите.
          </p>
        ) : null}
        {searchParameters.get('reset') === '1' ? (
          <p className="account-form-status" role="status">
            Пароль обновлён. Теперь войдите.
          </p>
        ) : null}

        <form className="auth-form" noValidate onSubmit={submitLogin}>
          <div className="form-field">
            <label htmlFor="login-identifier">Email или телефон</label>
            <input
              id="login-identifier"
              name="identifier"
              type="text"
              autoComplete="username"
              required
              autoFocus
              aria-invalid={Boolean(errorMessage)}
              aria-describedby={errorMessage ? 'login-form-error' : undefined}
              onChange={() => {
                setClientError(null)
                loginMutation.reset()
              }}
            />
          </div>
          <div className="form-field">
            <label htmlFor="login-password">Пароль</label>
            <input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              aria-invalid={Boolean(errorMessage)}
              aria-describedby={errorMessage ? 'login-form-error' : undefined}
              onChange={() => {
                setClientError(null)
                loginMutation.reset()
              }}
            />
          </div>
          {errorMessage ? (
            <p id="login-form-error" className="form-error" role="alert">
              {errorMessage}
            </p>
          ) : null}
          <button
            className="button button--primary auth-form__submit"
            type="submit"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? 'Входим…' : 'Войти'}
          </button>
        </form>

        <div className="auth-card__links">
          <p>
            Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
          </p>
          <Link to="/password/reset">Забыли пароль?</Link>
          <a href={legacyLoginUrl}>Прежняя версия входа</a>
        </div>
      </section>
    </div>
  )
}
