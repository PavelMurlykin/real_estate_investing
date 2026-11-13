import { describe, expect, it, vi } from 'vitest'
import { retryFailedQueries } from './retryFailedQueries'

describe('retryFailedQueries', () => {
  it('recovers failed dependencies once without requesting healthy or unused resources', async () => {
    const primary = { isError: true, refetch: vi.fn().mockResolvedValue('list') }
    const failed = { isError: true, refetch: vi.fn().mockResolvedValue('filters') }
    const healthy = { isError: false, refetch: vi.fn() }
    expect(await retryFailedQueries(primary, failed, failed, healthy, primary)).toEqual(['list', 'filters'])
    expect(primary.refetch).toHaveBeenCalledTimes(1)
    expect(failed.refetch).toHaveBeenCalledTimes(1)
    expect(healthy.refetch).not.toHaveBeenCalled()
  })
})
