{{GENERATED_HEADER}}
{{SEED_IMPORTS}}import type { MockState } from '../contract/index.ts'

export type SeedContext = {
  fromSeedNow: (days: number) => string
  seedNow: string
}

const seedNow = {{SEED_NOW}}
const dayMs = 24 * 60 * 60 * 1000

const newSeedContext = (): SeedContext => ({
  fromSeedNow: (days) => new Date(Date.parse(seedNow) + days * dayMs).toISOString(),
  seedNow,
})

export const seedState = (): MockState => {
  const context = newSeedContext()

  return {
    schemaVersion: {{SCHEMA_VERSION}},
    clock: {
      now: context.seedNow,
    },
{{FALLBACK_SLICE_SEEDS}}
{{FEATURE_SEED_SPREADS}}
  }
}
