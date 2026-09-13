import { useMutation, useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { requestPasswordReset, sessionQueryOptions } from '@/api/queries'
import {
  accountFormErrors,
  type AccountFormErrors,
} from '@/features/account/formErrors'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function PasswordResetRequestPage() {
  useDocumentTitle('Восстановление пароля')
  const sessionQuery = useQuery(sessionQueryOptions)
  const formReference = useRef<HTMLFormElement>(null)
  const [errors, setErrors] = useState<AccountFormErrors>({})
  const [isRequested, setIsRequested] = useState(false)
  const resetMutation = useMutation({
    mutationFn: requestPasswordReset,
    onSuccess: () => {
      formReference.current?.reset()
      setErrors({})
      setIsRequested(true)
    },
    onError: (error) => {
      setIsRequested(false)
      setErrors(accountFormErrors(
        error,
        'Не удалось отправить инструкцию. Повторите попытку.',
      ))
    },
  })

  const submitRequest = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    resetMutation.reset()
    setIsRequested(false)
    const formData = new FormData(event.currentTarget)
    const email = String(formData.get('email') ?? '').trim()
    if (!email) {
      setErrors({ email: 'Введите email.' })
      return
    }
    setErrors({})
    resetMutation.mutate({ email })
  }

  const clearMessages = () => {
    if (Object.keys(errors).length > 0) setErrors({})
    if (isRequested) setIsRequested(false)
    resetMutation.reset()
  }

  if (sessionQuery.isLoading) return <PageLoadingState />
  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }

  return (
    <div className="auth-page">
      <section className="auth-card" aria-labelledby="password-reset-title">
        <header className="auth-card__header">
          <span className="eyebrow">Доступ к аккаунту</span>
          <h1 id="password-reset-title">Восстановление пароля</h1>
          <p>
            Введите email аккаунта. Если он подходит для восстановления,
            мы отправим одноразовую ссылку.
          </p>
        </header>

        {isRequested ? (
          <div className="account-form-status" role="status">
            Инструкция отправлена, если аккаунт с таким email существует.
            Проверьте входящие сообщения и папку со спамом.
          </div>
        ) : null}

        <form
          ref={formReference}
          className="auth-form"
          noValidate
          onSubmit={submitRequest}
          onChange={clearMessages}
        >
          <div className="form-field">
            <label htmlFor="password-reset-email">Email</label>
            <input
              id="password-reset-email"
              name="email"
              type="email"
              autoComplete="email"
              autoFocus
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email
                ? 'password-reset-email-error'
                : undefined}
            />
            {errors.email ? (
              <span id="password-reset-email-error" className="field-error">
                {errors.email}
              </span>
            ) : null}
          </div>

          {errors.form ? (
            <p className="form-error" role="alert">{errors.form}</p>
          ) : null}
          <button
            className="button button--primary auth-form__submit"
            type="submit"
            disabled={resetMutation.isPending}
          >
            {resetMutation.isPending
              ? 'Отправляем инструкцию…'
              : 'Отправить инструкцию'}
          </button>
        </form>

        <div className="auth-card__links">
          <Link to="/login">Вернуться ко входу</Link>
          {sessionQuery.data?.isAuthenticated ? (
            <Link to="/password/change">Изменить пароль по текущему</Link>
          ) : null}
          <a href="/users/password/reset/">
            Прежняя версия восстановления
          </a>
        </div>
      </section>
    </div>
  )
}
