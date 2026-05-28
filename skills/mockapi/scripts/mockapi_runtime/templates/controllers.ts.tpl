{{STARTER_HEADER}}
{{PRODUCT_IMPORTS}}
import type { GeneratedMockControllers as AdminGeneratedMockControllers } from './generated/mock-admin/mock-runtime.ts'
import { newAdminStateController } from './generated/mock-admin/state/controller.ts'
import { MockStateRepository, type MockStateOptions } from './generated/mock-admin/state/repository.ts'
import { AdminStateService } from './generated/mock-admin/state/service.ts'
import { seedState } from './generated/mock-admin/state/seed.ts'
import type { MockState } from './generated/mock-admin/contract/index.ts'
{{OPERATION_IMPORTS}}

export type ProductMockControllers = {{PRODUCT_TYPES}}
export type MockApiControllers = ProductMockControllers & AdminGeneratedMockControllers
export type MockApiDependencies = {
  stateRepository: MockStateRepository
}

export const newMockApiControllers = (
  options: MockStateOptions = {},
): MockApiControllers => {
  const stateRepository = new MockStateRepository(options)
  const deps: MockApiDependencies = {
    stateRepository,
  }
  const adminStateService = new AdminStateService(stateRepository, {{OPERATION_COUNT}})

  return {
{{CONTROLLER_SPREADS}}
    ...newAdminStateController(adminStateService),
  } as MockApiControllers
}

export const newMemoryMockApiControllers = (
  initialState: MockState = seedState(),
): MockApiControllers => newMockApiControllers({ initialState })
