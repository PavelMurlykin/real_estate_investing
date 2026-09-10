import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

import { PageLoadingState } from '@/shared/ui/AsyncState'

import { AppShell } from './AppShell'

const HomePage = lazy(async () => ({
  default: (await import('@/pages/HomePage')).HomePage,
}))
const PropertyListPage = lazy(async () => ({
  default: (await import('@/pages/PropertyListPage')).PropertyListPage,
}))
const PropertyDetailPage = lazy(async () => ({
  default: (await import('@/pages/PropertyDetailPage')).PropertyDetailPage,
}))
const MortgageCalculatorPage = lazy(async () => ({
  default: (await import('@/pages/MortgageCalculatorPage'))
    .MortgageCalculatorPage,
}))
const SavedMortgageCalculationListPage = lazy(async () => ({
  default: (await import('@/pages/SavedMortgageCalculationListPage'))
    .SavedMortgageCalculationListPage,
}))
const SavedMortgageCalculationDetailPage = lazy(async () => ({
  default: (await import('@/pages/SavedMortgageCalculationDetailPage'))
    .SavedMortgageCalculationDetailPage,
}))
const NotFoundPage = lazy(async () => ({
  default: (await import('@/pages/NotFoundPage')).NotFoundPage,
}))

export function App() {
  return (
    <Suspense fallback={<PageLoadingState />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="properties" element={<PropertyListPage />} />
          <Route
            path="properties/:propertyId"
            element={<PropertyDetailPage />}
          />
          <Route path="mortgage" element={<MortgageCalculatorPage />} />
          <Route
            path="mortgage/calculations"
            element={<SavedMortgageCalculationListPage />}
          />
          <Route
            path="mortgage/calculations/:calculationId"
            element={<SavedMortgageCalculationDetailPage />}
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
