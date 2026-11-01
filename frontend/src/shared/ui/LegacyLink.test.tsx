import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { LegacyLink } from './LegacyLink'

describe('LegacyLink', () => {
  it('opens Django directly while retaining the object and result anchor', () => {
    renderWithProviders(<LegacyLink href="/mortgage/?property_id=3#result">Django</LegacyLink>)
    expect(screen.getByRole('link', { name: 'Django' })).toHaveAttribute('href', '/mortgage/?property_id=3&legacy=1#result')
  })
})
