import { useMutation, useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { registerUser, sessionQueryOptions } from '@/api/queries'
import type { RegistrationRequest } from '@/api/schemas'
import {
  accountFormErrors,
  type AccountFormErrors,
  type AccountFieldName,
} from '@/features/account/formErrors'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function fieldErrorId(fieldName: AccountFieldName) {
  return `registration-${fieldName}-error`
}

function RegistrationFieldError({
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

export function RegistrationPage() {
  useDocumentTitle('Регистрация')
  const navigate = useNavigate()
  const sessionQuery = useQuery(sessionQueryOptions)
  const [isRealEstateAgent, setIsRealEstateAgent] = useState(false)
  const [errors, setErrors] = useState<AccountFormErrors>({})
  const registrationMutation = useMutation({
    mutationFn: registerUser,
    onSuccess: () => navigate('/login?registered=1', { replace: true }),
    onError: (error) => setErrors(accountFormErrors(
      error,
      'Не удалось создать аккаунт. Повторите попытку.',
    )),
  })

  const submitRegistration = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    registrationMutation.reset()
    const formData = new FormData(event.currentTarget)
    const payload: RegistrationRequest = {
      firstName: String(formData.get('firstName') ?? '').trim(),
      lastName: String(formData.get('lastName') ?? '').trim(),
      email: String(formData.get('email') ?? '').trim(),
      phoneNumber: String(formData.get('phoneNumber') ?? '').trim(),
      isRealEstateAgent,
      agencyName: String(formData.get('agencyName') ?? '').trim(),
      password1: String(formData.get('password1') ?? ''),
      password2: String(formData.get('password2') ?? ''),
    }
    const clientErrors: AccountFormErrors = {}
    if (!payload.firstName) clientErrors.firstName = 'Введите имя.'
    if (!payload.lastName) clientErrors.lastName = 'Введите фамилию.'
    if (!payload.email) clientErrors.email = 'Введите email.'
    if (!payload.phoneNumber) clientErrors.phoneNumber = 'Введите телефон.'
    if (!payload.password1) clientErrors.password1 = 'Введите пароль.'
    if (!payload.password2) {
      clientErrors.password2 = 'Повторите пароль.'
    } else if (payload.password1 !== payload.password2) {
      clientErrors.password2 = 'Пароли не совпадают.'
    }
    if (isRealEstateAgent && !payload.agencyName) {
      clientErrors.agencyName = 'Укажите название агентства.'
    }
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0) return
    registrationMutation.mutate(payload)
  }

  const clearErrors = () => {
    if (Object.keys(errors).length > 0) setErrors({})
    registrationMutation.reset()
  }

  if (sessionQuery.isLoading) return <PageLoadingState />
  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }
  if (sessionQuery.data?.isAuthenticated) return <Navigate replace to="/" />

  return (
    <div className="auth-page">
      <section
        className="auth-card auth-card--wide"
        aria-labelledby="registration-title"
      >
        <header className="auth-card__header">
          <span className="eyebrow">Личный кабинет</span>
          <h1 id="registration-title">Регистрация</h1>
          <p>
            Создайте аккаунт для работы с клиентами и сохранёнными расчётами.
            Проверку данных и пароля выполняет существующая Django-форма.
          </p>
        </header>

        <form
          className="auth-form"
          noValidate
          onSubmit={submitRegistration}
          onChange={clearErrors}
        >
          <div className="account-form-grid">
            <div className="form-field">
              <label htmlFor="registration-first-name">Имя</label>
              <input
                id="registration-first-name"
                name="firstName"
                autoComplete="given-name"
                autoFocus
                aria-invalid={Boolean(errors.firstName)}
                aria-describedby={errors.firstName
                  ? fieldErrorId('firstName')
                  : undefined}
              />
              <RegistrationFieldError fieldName="firstName" errors={errors} />
            </div>
            <div className="form-field">
              <label htmlFor="registration-last-name">Фамилия</label>
              <input
                id="registration-last-name"
                name="lastName"
                autoComplete="family-name"
                aria-invalid={Boolean(errors.lastName)}
                aria-describedby={errors.lastName
                  ? fieldErrorId('lastName')
                  : undefined}
              />
              <RegistrationFieldError fieldName="lastName" errors={errors} />
            </div>
            <div className="form-field">
              <label htmlFor="registration-email">Email</label>
              <input
                id="registration-email"
                name="email"
                type="email"
                autoComplete="email"
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email
                  ? fieldErrorId('email')
                  : undefined}
              />
              <RegistrationFieldError fieldName="email" errors={errors} />
            </div>
            <div className="form-field">
              <label htmlFor="registration-phone">Телефон</label>
              <input
                id="registration-phone"
                name="phoneNumber"
                type="tel"
                autoComplete="tel"
                aria-invalid={Boolean(errors.phoneNumber)}
                aria-describedby={errors.phoneNumber
                  ? fieldErrorId('phoneNumber')
                  : undefined}
              />
              <RegistrationFieldError fieldName="phoneNumber" errors={errors} />
            </div>
            <div className="form-field">
              <label htmlFor="registration-password">Пароль</label>
              <input
                id="registration-password"
                name="password1"
                type="password"
                autoComplete="new-password"
                aria-invalid={Boolean(errors.password1)}
                aria-describedby={errors.password1
                  ? fieldErrorId('password1')
                  : undefined}
              />
              <RegistrationFieldError fieldName="password1" errors={errors} />
            </div>
            <div className="form-field">
              <label htmlFor="registration-password-repeat">
                Подтверждение пароля
              </label>
              <input
                id="registration-password-repeat"
                name="password2"
                type="password"
                autoComplete="new-password"
                aria-invalid={Boolean(errors.password2)}
                aria-describedby={errors.password2
                  ? fieldErrorId('password2')
                  : undefined}
              />
              <RegistrationFieldError fieldName="password2" errors={errors} />
            </div>
            <label className="account-checkbox form-field--wide">
              <input
                name="isRealEstateAgent"
                type="checkbox"
                aria-label="Я агент недвижимости"
                checked={isRealEstateAgent}
                onChange={(event) => {
                  setIsRealEstateAgent(event.currentTarget.checked)
                  clearErrors()
                }}
              />
              <span>
                <strong>Я агент недвижимости</strong>
                <small>Добавьте название агентства в профиль.</small>
              </span>
            </label>
            <div className="form-field form-field--wide">
              <label htmlFor="registration-agency">Название агентства</label>
              <input
                id="registration-agency"
                name="agencyName"
                disabled={!isRealEstateAgent}
                aria-invalid={Boolean(errors.agencyName)}
                aria-describedby={errors.agencyName
                  ? fieldErrorId('agencyName')
                  : undefined}
              />
              <RegistrationFieldError fieldName="agencyName" errors={errors} />
            </div>
          </div>

          {errors.form ? (
            <p className="form-error" role="alert">{errors.form}</p>
          ) : null}
          <button
            className="button button--primary auth-form__submit"
            type="submit"
            disabled={registrationMutation.isPending}
          >
            {registrationMutation.isPending
              ? 'Создаём аккаунт…'
              : 'Зарегистрироваться'}
          </button>
        </form>

        <div className="auth-card__links">
          <p>Уже есть аккаунт? <Link to="/login">Войти</Link></p>
          <a href="/users/register/">Прежняя версия регистрации</a>
        </div>
      </section>
    </div>
  )
}
