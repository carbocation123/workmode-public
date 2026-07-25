export function createStartupUpdateCheck<T>(
  check: () => Promise<T>,
  onError: (error: unknown) => void = () => undefined,
): () => Promise<T | null> {
  let pending: Promise<T | null> | null = null

  return () => {
    if (!pending) {
      pending = check().catch((error) => {
        onError(error)
        return null
      })
    }
    return pending
  }
}
