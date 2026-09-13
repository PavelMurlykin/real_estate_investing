import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  confirmPasswordReset,
  sessionQueryOptions,
} from '@/api/queries'
import type { PasswordResetConfirmRequest } from '@/api/schemas'
import {
  accountFormErrors,
  type AccountFormErrors,
} from '@/features/account/formErrors'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function PasswordResetConfirmPage() {
  useDocumentTitle('Новый пароль')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const [errors, setErrors] = useState<AccountFormErrors>({})
  const confirmMutation = useMutation({
    mutationFn: confirmPasswordReset,
    onSuccess: (result) => {
      queryClient.setQueryData(['session'], result.session)
      navigate('/login?reset=1', { replace: true })
    },
    onError: (error) => setErrors(accountFormErrors(
      error,
      'Не удалось установить новый пароль. Повторите попытку.',
    )),
  })

  const submitPassword = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    confirmMutation.reset()
    const formData = new FormData(event.currentTarget)
    const payload: PasswordResetConfirmRequest = {
      newPassword1: String(formData.get('newPassword1') ?? ''),
      newPassword2: String(formData.get('newPassword2') ?? ''),
    }
    const clientErrors: AccountFormErrors = {}
    if (!payload.newPassword1) {
      clientErrors.newPassword1 = 'Введите новый пароль.'
    }
    if (!payload.newPassword2) {
      clientErrors.newPassword2 = 'Повторите новый пароль.'
    } else if (payload.newPassword1 !== payload.newPassword2) {
      clientErrors.newPassword2 = 'Новые пароли не совпадают.'
    }
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0) return
    confirmMutation.mutate(payload)
  }

  const clearErrors = () => {
    if (Object.keys(errors).length > 0) setErrors({})
    confirmMutation.reset()
  }

  if (sessionQuery.isLoading) return <PageLoadingState />
  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }

  return (
    <div className="auth-page">
      <section className="auth-card" aria-labelledby="reset-confirm-title">
        <header className="auth-card__header">
          <span className="eyebrow">Доступ к аккаунту</span>
          <h1 id="reset-confirm-title">Новый пароль</h1>
          <p>
            Задайте новый пароль для аккаунта. Все правила сложности
            проверяются на сервере.
          </p>
        </header>

        <form
          className="auth-form"
          noValidate
          onSubmit={submitPassword}
          onChange={clearErrors}
        >
          <div className="form-field">
            <label htmlFor="reset-confirm-password">Новый пароль</label>
            <input
              id="reset-confirm-password"
              name="newPassword1"
              type="password"
              autoComplete="new-password"
              autoFocus
              aria-invalid={Boolean(errors.newPassword1)}
              aria-describedby={errors.newPassword1
                ? 'reset-confirm-password-error'
                : undefined}
            />
            {errors.newPassword1 ? (
              <span
                id="reset-confirm-password-error"
                className="field-error"
              >
                {errors.newPassword1}
              </span>
            ) : null}
          </div>
          <div className="form-field">
            <label htmlFor="reset-confirm-password-repeat">
              Подтверждение нового пароля
            </label>
            <input
              id="reset-confirm-password-repeat"
              name="newPassword2"
              type="password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.newPassword2)}
              aria-describedby={errors.newPassword2
                ? 'reset-confirm-password-repeat-error'
                : undefined}
            />
            {errors.newPassword2 ? (
              <span
                id="reset-confirm-password-repeat-error"
                className="field-error"
              >
                {errors.newPassword2}
              </span>
            ) : null}
          </div>

          {errors.token || errors.form ? (
            <p className="form-error" role="alert">
              {errors.token ?? errors.form}
            </p>
          ) : null}
          <button
            className="button button--primary auth-form__submit"
            type="submit"
            disabled={confirmMutation.isPending}
          >
            {confirmMutation.isPending
              ? 'Сохраняем пароль…'
              : 'Сохранить новый пароль'}
          </button>
        </form>

        <div className="auth-card__links">
          <Link to="/password/reset">Запросить новую ссылку</Link>
          <a href="/users/password/reset/">
            Прежняя версия восстановления
          </a>
        </div>
      </section>
    </div>
  )
}
