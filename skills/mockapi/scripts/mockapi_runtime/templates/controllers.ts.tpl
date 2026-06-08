{{STARTER_HEADER}}
{{PRODUCT_IMPORTS}}
import type { GeneratedMockControllers as AdminGeneratedMockControllers } from './generated/mock-admin/mock-runtime.ts'
import { newAdminStateController } from './generated/mock-admin/state/controller.ts'
import { AdminStateService } from './generated/mock-admin/state/service.ts'
import { seedState } from './generated/mock-admin/state/seed.ts'
import type { MockState } from './generated/mock-admin/contract/index.ts'
import {
  newMockApiDependencies,
  type MockApiDependencies,
} from './dependencies.ts'
import {
  newFileMockStateStore,
  type MockStateOptions,
} from './lib/nodeStateStore.ts'
{{OPERATION_IMPORTS}}

export type ProductMockControllers = {{PRODUCT_TYPES}}
export type MockApiControllers = ProductMockControllers & AdminGeneratedMockControllers
export type { MockApiDependencies }

export const newMockApiControllers = async (
  options: MockStateOptions = {},
): Promise<MockApiControllers> => {
  const stateStore = await newFileMockStateStore(options)
  const deps = newMockApiDependencies(stateStore)
  const adminStateService = new AdminStateService(stateStore, {{OPERATION_COUNT}})

  return {
{{CONTROLLER_SPREADS}}
    ...newAdminStateController(adminStateService),
  } as MockApiControllers
}

export const newMemoryMockApiControllers = async (
  initialState: MockState = seedState(),
): Promise<MockApiControllers> => newMockApiControllers({ initialState })
