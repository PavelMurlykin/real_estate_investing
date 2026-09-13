import { ApiError } from '@/api/client'

export type AccountFieldName =
  | 'firstName'
  | 'lastName'
  | 'email'
  | 'phoneNumber'
  | 'isRealEstateAgent'
  | 'agencyName'
  | 'password1'
  | 'password2'
  | 'oldPassword'
  | 'newPassword1'
  | 'newPassword2'
  | 'form'

export type AccountFormErrors = Partial<Record<AccountFieldName, string>>

const accountFieldNames: AccountFieldName[] = [
  'firstName',
  'lastName',
  'email',
  'phoneNumber',
  'isRealEstateAgent',
  'agencyName',
  'password1',
  'password2',
  'oldPassword',
  'newPassword1',
  'newPassword2',
]

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

export function accountFormErrors(
  error: unknown,
  fallbackMessage: string,
): AccountFormErrors {
  if (
    !(error instanceof ApiError)
    || !error.details
    || typeof error.details !== 'object'
    || Array.isArray(error.details)
  ) {
    return { form: fallbackMessage }
  }

  const details = error.details as Record<string, unknown>
  const rawErrors = (
    details.errors
    && typeof details.errors === 'object'
    && !Array.isArray(details.errors)
  )
    ? details.errors as Record<string, unknown>
    : {}
  const errors: AccountFormErrors = {}
  for (const fieldName of accountFieldNames) {
    const message = firstMessage(rawErrors[fieldName])
    if (message) errors[fieldName] = message
  }
  const formMessage = firstMessage(rawErrors.nonFieldErrors)
    ?? firstMessage(details.detail)
  if (formMessage) errors.form = formMessage
  if (Object.keys(errors).length === 0) errors.form = error.message
  return errors
}
