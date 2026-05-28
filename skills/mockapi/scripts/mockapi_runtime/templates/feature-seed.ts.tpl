{{STARTER_HEADER}}
import type { SeedContext } from '../../generated/mock-admin/state/seed.ts'
import type { MockState } from '../../generated/mock-admin/contract/index.ts'

export const {{FUNCTION_NAME}} = (_context: SeedContext): Pick<MockState, {{PICK_KEYS}}> => ({
{{SLICE_SEEDS}}
})
