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
const PropertyFormPage = lazy(async () => ({
  default: (await import('@/pages/PropertyFormPage')).PropertyFormPage,
}))
const CompanyGroupListPage = lazy(async () => ({
  default: (await import('@/pages/CompanyGroupListPage')).CompanyGroupListPage,
}))
const CompanyGroupFormPage = lazy(async () => ({
  default: (await import('@/pages/CompanyGroupFormPage')).CompanyGroupFormPage,
}))
const DeveloperListPage = lazy(async () => ({
  default: (await import('@/pages/DeveloperListPage')).DeveloperListPage,
}))
const DeveloperFormPage = lazy(async () => ({
  default: (await import('@/pages/DeveloperFormPage')).DeveloperFormPage,
}))
const RealEstateComplexListPage = lazy(async () => ({
  default: (await import('@/pages/RealEstateComplexListPage'))
    .RealEstateComplexListPage,
}))
const RealEstateComplexDetailPage = lazy(async () => ({
  default: (await import('@/pages/RealEstateComplexDetailPage'))
    .RealEstateComplexDetailPage,
}))
const RealEstateComplexFormPage = lazy(async () => ({
  default: (await import('@/pages/RealEstateComplexFormPage'))
    .RealEstateComplexFormPage,
}))
const PropertyDictionaryPage = lazy(async () => ({
  default: (await import('@/pages/PropertyDictionaryPage'))
    .PropertyDictionaryPage,
}))
const LocationDictionaryPage = lazy(async () => ({
  default: (await import('@/pages/LocationDictionaryPage'))
    .LocationDictionaryPage,
}))
const BankListPage = lazy(async () => ({
  default: (await import('@/pages/BankListPage')).BankListPage,
}))
const BankDetailPage = lazy(async () => ({
  default: (await import('@/pages/BankDetailPage')).BankDetailPage,
}))
const BankFormPage = lazy(async () => ({
  default: (await import('@/pages/BankFormPage')).BankFormPage,
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
          <Route path="properties/new" element={<PropertyFormPage />} />
          <Route
            path="properties/:propertyId"
            element={<PropertyDetailPage />}
          />
          <Route
            path="properties/:propertyId/edit"
            element={<PropertyFormPage />}
          />
          <Route path="company-groups" element={<CompanyGroupListPage />} />
          <Route
            path="company-groups/new"
            element={<CompanyGroupFormPage />}
          />
          <Route
            path="company-groups/:companyGroupId/edit"
            element={<CompanyGroupFormPage />}
          />
          <Route path="developers" element={<DeveloperListPage />} />
          <Route path="developers/new" element={<DeveloperFormPage />} />
          <Route
            path="developers/:developerId/edit"
            element={<DeveloperFormPage />}
          />
          <Route path="complexes" element={<RealEstateComplexListPage />} />
          <Route
            path="complexes/new"
            element={<RealEstateComplexFormPage />}
          />
          <Route
            path="complexes/:complexId"
            element={<RealEstateComplexDetailPage />}
          />
          <Route
            path="complexes/:complexId/edit"
            element={<RealEstateComplexFormPage />}
          />
          <Route
            path="dictionaries/:dictionaryKey"
            element={<PropertyDictionaryPage />}
          />
          <Route
            path="dictionaries/:dictionaryKey/:entryId/edit"
            element={<PropertyDictionaryPage />}
          />
          <Route
            path="locations/:dictionaryKey"
            element={<LocationDictionaryPage />}
          />
          <Route
            path="locations/:dictionaryKey/:entryId/edit"
            element={<LocationDictionaryPage />}
          />
          <Route path="banks" element={<BankListPage />} />
          <Route path="banks/new" element={<BankFormPage />} />
          <Route path="banks/:bankId" element={<BankDetailPage />} />
          <Route path="banks/:bankId/edit" element={<BankFormPage />} />
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
