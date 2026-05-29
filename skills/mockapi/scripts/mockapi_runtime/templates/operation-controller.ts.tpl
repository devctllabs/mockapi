{{STARTER_HEADER}}
import type { MockApiDependencies, ProductMockControllers } from '../../../controllers.ts'

export const {{FACTORY_NAME}} = (
  _deps: MockApiDependencies,
): Pick<ProductMockControllers, {{PICK_KEYS}}> => ({
{{CONTROLLER_METHODS}}
})
