import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

export function renderWithProviders(
  element: ReactElement,
  {
    initialRoute = '/',
    queryClient = createTestQueryClient(),
  }: {
    initialRoute?: string
    queryClient?: QueryClient
  } = {},
) {
  if (!queryClient.getQueryData(['session'])) {
    queryClient.setQueryData(['session'], {
      isAuthenticated: false,
      user: null,
      capabilities: {
        manageCatalogs: false,
        syncExternalData: false,
        viewPrivateRecords: false,
        viewAllPrivateRecords: false,
      },
    })
  }

  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialRoute]}>{element}</MemoryRouter>
      </QueryClientProvider>,
    ),
  }
}
