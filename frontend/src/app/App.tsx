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
const CustomerListPage = lazy(async () => ({
  default: (await import('@/pages/CustomerListPage')).CustomerListPage,
}))
const CustomerDetailPage = lazy(async () => ({
  default: (await import('@/pages/CustomerDetailPage')).CustomerDetailPage,
}))
const CustomerFormPage = lazy(async () => ({
  default: (await import('@/pages/CustomerFormPage')).CustomerFormPage,
}))
const MortgageCalculatorPage = lazy(async () => ({
  default: (await import('@/pages/MortgageCalculatorPage'))
    .MortgageCalculatorPage,
}))
const TrenchMortgageCalculatorPage = lazy(async () => ({
  default: (await import('@/pages/TrenchMortgageCalculatorPage'))
    .TrenchMortgageCalculatorPage,
}))
const SavedMortgageCalculationListPage = lazy(async () => ({
  default: (await import('@/pages/SavedMortgageCalculationListPage'))
    .SavedMortgageCalculationListPage,
}))
const SavedMortgageCalculationDetailPage = lazy(async () => ({
  default: (await import('@/pages/SavedMortgageCalculationDetailPage'))
    .SavedMortgageCalculationDetailPage,
}))
const SavedTrenchMortgageCalculationListPage = lazy(async () => ({
  default: (
    await import('@/pages/SavedTrenchMortgageCalculationListPage')
  ).SavedTrenchMortgageCalculationListPage,
}))
const SavedTrenchMortgageCalculationDetailPage = lazy(async () => ({
  default: (
    await import('@/pages/SavedTrenchMortgageCalculationDetailPage')
  ).SavedTrenchMortgageCalculationDetailPage,
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
          <Route path="customers" element={<CustomerListPage />} />
          <Route path="customers/new" element={<CustomerFormPage />} />
          <Route
            path="customers/:customerId"
            element={<CustomerDetailPage />}
          />
          <Route
            path="customers/:customerId/edit"
            element={<CustomerFormPage />}
          />
          <Route path="mortgage" element={<MortgageCalculatorPage />} />
          <Route
            path="mortgage/trench"
            element={<TrenchMortgageCalculatorPage />}
          />
          <Route
            path="mortgage/calculations"
            element={<SavedMortgageCalculationListPage />}
          />
          <Route
            path="mortgage/calculations/:calculationId"
            element={<SavedMortgageCalculationDetailPage />}
          />
          <Route
            path="mortgage/trench/calculations"
            element={<SavedTrenchMortgageCalculationListPage />}
          />
          <Route
            path="mortgage/trench/calculations/:calculationId"
            element={<SavedTrenchMortgageCalculationDetailPage />}
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
