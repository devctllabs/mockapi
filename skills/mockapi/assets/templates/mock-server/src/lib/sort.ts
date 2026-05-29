// @ts-nocheck -- mockapi template source; stripped during generation
export const byStringField =
  <T extends Record<string, unknown>>(field: keyof T, direction: 'asc' | 'desc' = 'asc') =>
  (left: T, right: T) => {
    const leftValue = String(left[field] ?? '')
    const rightValue = String(right[field] ?? '')
    const result = leftValue.localeCompare(rightValue)

    return direction === 'asc' ? result : -result
  }
