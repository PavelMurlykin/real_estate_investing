import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  sessionQueryOptions,
  validatePasswordResetToken,
} from '@/api/queries'
import {
  accountFormErrors,
  type AccountFormErrors,
} from '@/features/account/formErrors'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function PasswordResetTokenPage() {
  useDocumentTitle('Проверка ссылки')
  const navigate = useNavigate()
  const { userIdentifier, token } = useParams()
  const sessionQuery = useQuery(sessionQueryOptions)
  const validationStarted = useRef(false)
  const [errors, setErrors] = useState<AccountFormErrors>({})
  const tokenMutation = useMutation({
    mutationFn: validatePasswordResetToken,
    onSuccess: () => {
      navigate('/password/reset/confirm', { replace: true })
    },
    onError: (error) => {
      setErrors(accountFormErrors(
        error,
        'Ссылка для восстановления недействительна или устарела.',
      ))
    },
  })

  useEffect(() => {
    if (
      !sessionQuery.isSuccess
      || !userIdentifier
      || !token
      || validationStarted.current
    ) {
      return
    }
    validationStarted.current = true
    tokenMutation.mutate({ userIdentifier, token })
  }, [
    sessionQuery.isSuccess,
    token,
    tokenMutation,
    userIdentifier,
  ])

  if (sessionQuery.isError) {
    return <ErrorState onRetry={() => void sessionQuery.refetch()} />
  }
  if (errors.token || errors.form) {
    return (
      <div className="auth-page">
        <section className="auth-card" aria-labelledby="reset-link-error-title">
          <header className="auth-card__header">
            <span className="eyebrow">Доступ к аккаунту</span>
            <h1 id="reset-link-error-title">Ссылка не работает</h1>
            <p role="alert">
              {errors.token ?? errors.form}
            </p>
          </header>
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
  return <PageLoadingState />
}
