/**
 * Extract a human-readable error message from a Django Ninja error response body.
 * Falls back to `fallback` when no structured message is found.
 */
export function extractErrorMessage(data: unknown, fallback: string): string {
  const errData = data as Record<string, unknown> | null | undefined
  if (!errData) return fallback
  if (typeof errData.detail === 'string') return errData.detail
  const firstKey = Object.keys(errData).at(0)
  if (firstKey === undefined) return fallback
  const firstVal = errData[firstKey]
  if (Array.isArray(firstVal)) return `${firstKey}: ${firstVal[0]}`
  return `${firstKey}: ${String(firstVal)}`
}
