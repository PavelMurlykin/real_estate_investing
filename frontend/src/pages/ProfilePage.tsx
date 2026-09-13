import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'

import {
  sessionQueryOptions,
  updateUserProfile,
  userProfileQueryOptions,
} from '@/api/queries'
import type {
  Session,
  UserProfile,
  UserProfileWriteRequest,
} from '@/api/schemas'
import {
  accountFormErrors,
  type AccountFormErrors,
  type AccountFieldName,
} from '@/features/account/formErrors'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function fieldErrorId(fieldName: AccountFieldName) {
  return `profile-${fieldName}-error`
}

function ProfileFieldError({
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

function ProfileForm({ profile }: { profile: UserProfile }) {
  const queryClient = useQueryClient()
  const [isRealEstateAgent, setIsRealEstateAgent] = useState(
    profile.isRealEstateAgent,
  )
  const [errors, setErrors] = useState<AccountFormErrors>({})
  const [isSaved, setIsSaved] = useState(false)
  const profileMutation = useMutation({
    mutationFn: updateUserProfile,
    onSuccess: (updatedProfile) => {
      queryClient.setQueryData(['user-profile'], updatedProfile)
      queryClient.setQueryData<Session>(['session'], (currentSession) => {
        if (!currentSession?.user) return currentSession
        const displayName = [
          updatedProfile.firstName,
          updatedProfile.lastName,
        ].filter(Boolean).join(' ') || updatedProfile.email
        return {
          ...currentSession,
          user: {
            ...currentSession.user,
            displayName,
            email: updatedProfile.email,
            agencyName: updatedProfile.agencyName,
          },
        }
      })
      setErrors({})
      setIsSaved(true)
    },
    onError: (error) => {
      setIsSaved(false)
      setErrors(accountFormErrors(
        error,
        'Не удалось сохранить профиль. Повторите попытку.',
      ))
    },
  })

  const submitProfile = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    profileMutation.reset()
    setIsSaved(false)
    const formData = new FormData(event.currentTarget)
    const payload: UserProfileWriteRequest = {
      firstName: String(formData.get('firstName') ?? '').trim(),
      lastName: String(formData.get('lastName') ?? '').trim(),
      email: String(formData.get('email') ?? '').trim(),
      phoneNumber: String(formData.get('phoneNumber') ?? '').trim(),
      isRealEstateAgent,
      agencyName: String(formData.get('agencyName') ?? '').trim(),
    }
    const clientErrors: AccountFormErrors = {}
    if (!payload.firstName) clientErrors.firstName = 'Введите имя.'
    if (!payload.lastName) clientErrors.lastName = 'Введите фамилию.'
    if (!payload.email) clientErrors.email = 'Введите email.'
    if (!payload.phoneNumber) clientErrors.phoneNumber = 'Введите телефон.'
    if (isRealEstateAgent && !payload.agencyName) {
      clientErrors.agencyName = 'Укажите название агентства.'
    }
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0) return
    profileMutation.mutate(payload)
  }

  const clearMessages = () => {
    if (Object.keys(errors).length > 0) setErrors({})
    if (isSaved) setIsSaved(false)
    profileMutation.reset()
  }

  return (
    <form
      className="auth-form"
      noValidate
      onSubmit={submitProfile}
      onChange={clearMessages}
    >
      <div className="account-form-grid">
        <div className="form-field">
          <label htmlFor="profile-first-name">Имя</label>
          <input
            id="profile-first-name"
            name="firstName"
            defaultValue={profile.firstName}
            autoComplete="given-name"
            autoFocus
            aria-invalid={Boolean(errors.firstName)}
            aria-describedby={errors.firstName
              ? fieldErrorId('firstName')
              : undefined}
          />
          <ProfileFieldError fieldName="firstName" errors={errors} />
        </div>
        <div className="form-field">
          <label htmlFor="profile-last-name">Фамилия</label>
          <input
            id="profile-last-name"
            name="lastName"
            defaultValue={profile.lastName}
            autoComplete="family-name"
            aria-invalid={Boolean(errors.lastName)}
            aria-describedby={errors.lastName
              ? fieldErrorId('lastName')
              : undefined}
          />
          <ProfileFieldError fieldName="lastName" errors={errors} />
        </div>
        <div className="form-field">
          <label htmlFor="profile-email">Email</label>
          <input
            id="profile-email"
            name="email"
            type="email"
            defaultValue={profile.email}
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email
              ? fieldErrorId('email')
              : undefined}
          />
          <ProfileFieldError fieldName="email" errors={errors} />
        </div>
        <div className="form-field">
          <label htmlFor="profile-phone">Телефон</label>
          <input
            id="profile-phone"
            name="phoneNumber"
            type="tel"
            defaultValue={profile.phoneNumber}
            autoComplete="tel"
            aria-invalid={Boolean(errors.phoneNumber)}
            aria-describedby={errors.phoneNumber
              ? fieldErrorId('phoneNumber')
              : undefined}
          />
          <ProfileFieldError fieldName="phoneNumber" errors={errors} />
        </div>
        <label className="account-checkbox form-field--wide">
          <input
            name="isRealEstateAgent"
            type="checkbox"
            aria-label="Я агент недвижимости"
            checked={isRealEstateAgent}
            onChange={(event) => {
              setIsRealEstateAgent(event.currentTarget.checked)
              clearMessages()
            }}
          />
          <span>
            <strong>Я агент недвижимости</strong>
            <small>Название агентства будет показано в панели аккаунта.</small>
          </span>
        </label>
        <div className="form-field form-field--wide">
          <label htmlFor="profile-agency">Название агентства</label>
          <input
            id="profile-agency"
            name="agencyName"
            defaultValue={profile.agencyName}
            disabled={!isRealEstateAgent}
            aria-invalid={Boolean(errors.agencyName)}
            aria-describedby={errors.agencyName
              ? fieldErrorId('agencyName')
              : undefined}
          />
          <ProfileFieldError fieldName="agencyName" errors={errors} />
        </div>
      </div>

      {errors.form ? (
        <p className="form-error" role="alert">{errors.form}</p>
      ) : null}
      {isSaved ? (
        <p className="account-form-status" role="status">
          Профиль сохранён.
        </p>
      ) : null}
      <div className="account-form-actions">
        <button
          className="button button--primary"
          type="submit"
          disabled={profileMutation.isPending}
        >
          {profileMutation.isPending ? 'Сохраняем…' : 'Сохранить профиль'}
        </button>
        <a className="button button--secondary" href="/users/password/change/">
          Сменить пароль
        </a>
      </div>
    </form>
  )
}

export function ProfilePage() {
  useDocumentTitle('Профиль')
  const sessionQuery = useQuery(sessionQueryOptions)
  const profileQuery = useQuery({
    ...userProfileQueryOptions,
    enabled: sessionQuery.data?.isAuthenticated === true,
  })

  if (sessionQuery.isLoading) return <PageLoadingState />
  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }
  if (!sessionQuery.data?.isAuthenticated) {
    return <Navigate replace to="/login?next=%2Fapp%2Fprofile" />
  }
  if (profileQuery.isLoading) return <PageLoadingState />
  if (profileQuery.isError || !profileQuery.data) {
    return <ErrorState onRetry={() => void profileQuery.refetch()} />
  }

  return (
    <div className="auth-page">
      <section
        className="auth-card auth-card--wide"
        aria-labelledby="profile-title"
      >
        <header className="auth-card__header">
          <span className="eyebrow">Личный кабинет</span>
          <h1 id="profile-title">Профиль</h1>
          <p>
            Обновите контактные данные. Сервер проверит уникальность email и
            телефона перед сохранением.
          </p>
        </header>

        <ProfileForm profile={profileQuery.data} />

        <div className="auth-card__links">
          <a href="/users/profile/edit/">Прежняя версия профиля</a>
        </div>
      </section>
    </div>
  )
}
