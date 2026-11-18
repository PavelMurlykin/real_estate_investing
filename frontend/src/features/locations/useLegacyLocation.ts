import { useQuery } from '@tanstack/react-query'

import { requestJson } from '@/api/client'
import { geographicPageSchema } from './geography'

export function useLegacyLocation(parameter: 'legacyCityId' | 'legacyRegionLookupId', id: string) {
  return useQuery({
    queryKey: ['legacy-location', parameter, id],
    enabled: /^[1-9][0-9]{0,18}$/.test(id),
    queryFn: ({ signal }) => requestJson(
      `/api/v1/locations/?${new URLSearchParams({ [parameter]: id })}`, geographicPageSchema, { signal },
    ),
    select: (page) => page.results[0],
  })
}
