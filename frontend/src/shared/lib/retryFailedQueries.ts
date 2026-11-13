type RetryableQuery = { isError: boolean; refetch: () => Promise<unknown> }

export function retryFailedQueries(primary: RetryableQuery, ...dependencies: RetryableQuery[]) {
  const queries = [...new Set([primary, ...dependencies.filter((query) => query.isError)])]
  return Promise.all(queries.map((query) => query.refetch()))
}
