import { useMutation, useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useRef, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import { changePassword, sessionQueryOptions } from '@/api/queries'
import type { PasswordChangeRequest } from '@/api/schemas'
import {
  accountFormErrors,
  type AccountFieldName,
  type AccountFormErrors,
} from '@/features/account/formErrors'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function fieldErrorId(fieldName: AccountFieldName) {
  return `password-change-${fieldName}-error`
}

function PasswordFieldError({
  fieldName,
  errors,
}: {
  fieldName: AccountFieldName
  errors: AccountFormErrors
}) {
  const message = errors[fieldName]
  return message ? (
    <span id={fieldErrorId(fieldName)} className="field-error">
      {message}
    </span>
  ) : null
}

export function PasswordChangePage() {
  useDocumentTitle('Смена пароля')
  const sessionQuery = useQuery(sessionQueryOptions)
  const formReference = useRef<HTMLFormElement>(null)
  const [errors, setErrors] = useState<AccountFormErrors>({})
  const [isChanged, setIsChanged] = useState(false)
  const passwordChangeMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      formReference.current?.reset()
      setErrors({})
      setIsChanged(true)
    },
    onError: (error) => {
      setIsChanged(false)
      setErrors(accountFormErrors(
        error,
        'Не удалось изменить пароль. Повторите попытку.',
      ))
    },
  })

  const submitPasswordChange = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    passwordChangeMutation.reset()
    setIsChanged(false)
    const formData = new FormData(event.currentTarget)
    const payload: PasswordChangeRequest = {
      oldPassword: String(formData.get('oldPassword') ?? ''),
      newPassword1: String(formData.get('newPassword1') ?? ''),
      newPassword2: String(formData.get('newPassword2') ?? ''),
    }
    const clientErrors: AccountFormErrors = {}
    if (!payload.oldPassword) {
      clientErrors.oldPassword = 'Введите текущий пароль.'
    }
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
    passwordChangeMutation.mutate(payload)
  }

  const clearMessages = () => {
    if (Object.keys(errors).length > 0) setErrors({})
    if (isChanged) setIsChanged(false)
    passwordChangeMutation.reset()
  }

  if (sessionQuery.isLoading) return <PageLoadingState />
  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }
  if (!sessionQuery.data?.isAuthenticated) {
    return (
      <Navigate
        replace
        to="/login?next=%2Fapp%2Fpassword%2Fchange"
      />
    )
  }

  return (
    <div className="auth-page">
      <section className="auth-card" aria-labelledby="password-change-title">
        <header className="auth-card__header">
          <span className="eyebrow">Безопасность аккаунта</span>
          <h1 id="password-change-title">Смена пароля</h1>
          <p>
            Подтвердите текущий пароль и задайте новый. После изменения
            текущая сессия останется активной.
          </p>
        </header>

        {isChanged ? (
          <p className="account-form-status" role="status">
            Пароль успешно изменён.
          </p>
        ) : null}

        <form
          ref={formReference}
          className="auth-form"
          noValidate
          onSubmit={submitPasswordChange}
          onChange={clearMessages}
        >
          <div className="form-field">
            <label htmlFor="password-change-old">Текущий пароль</label>
            <input
              id="password-change-old"
              name="oldPassword"
              type="password"
              autoComplete="current-password"
              autoFocus
              aria-invalid={Boolean(errors.oldPassword)}
              aria-describedby={errors.oldPassword
                ? fieldErrorId('oldPassword')
                : undefined}
            />
            <PasswordFieldError fieldName="oldPassword" errors={errors} />
          </div>
          <div className="form-field">
            <label htmlFor="password-change-new">Новый пароль</label>
            <input
              id="password-change-new"
              name="newPassword1"
              type="password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.newPassword1)}
              aria-describedby={errors.newPassword1
                ? fieldErrorId('newPassword1')
                : undefined}
            />
            <PasswordFieldError fieldName="newPassword1" errors={errors} />
          </div>
          <div className="form-field">
            <label htmlFor="password-change-repeat">
              Подтверждение нового пароля
            </label>
            <input
              id="password-change-repeat"
              name="newPassword2"
              type="password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.newPassword2)}
              aria-describedby={errors.newPassword2
                ? fieldErrorId('newPassword2')
                : undefined}
            />
            <PasswordFieldError fieldName="newPassword2" errors={errors} />
          </div>

          {errors.form ? (
            <p className="form-error" role="alert">{errors.form}</p>
          ) : null}
          <button
            className="button button--primary auth-form__submit"
            type="submit"
            disabled={passwordChangeMutation.isPending}
          >
            {passwordChangeMutation.isPending
              ? 'Изменяем пароль…'
              : 'Изменить пароль'}
          </button>
        </form>

        <div className="auth-card__links">
          <Link to="/profile">Вернуться в профиль</Link>
          <a href="/users/password/change/">Прежняя версия смены пароля</a>
        </div>
      </section>
    </div>
  )
}
