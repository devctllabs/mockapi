// @ts-nocheck -- mockapi template source; stripped during generation
export const newIdAllocator = (counters: Record<string, number>) => ({
  next(prefix: string) {
    const value = counters[prefix] ?? 1
    counters[prefix] = value + 1

    return `${prefix}-${value}`
  },
})
