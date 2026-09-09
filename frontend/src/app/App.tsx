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
const MortgageCalculatorPage = lazy(async () => ({
  default: (await import('@/pages/MortgageCalculatorPage'))
    .MortgageCalculatorPage,
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
          <Route path="mortgage" element={<MortgageCalculatorPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
