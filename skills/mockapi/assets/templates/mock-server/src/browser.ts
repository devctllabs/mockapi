// @ts-nocheck -- mockapi template source; stripped during generation
export {
  newMockApiDependencies,
  type MockApiDependencies,
} from './dependencies.ts'
export {
  newBrowserMockStateStore,
  type BrowserMockStateStoreOptions,
} from './lib/browserStateStore.ts'
export { seedState } from './generated/mock-admin/state/seed.ts'
export { zMockState } from './generated/mock-admin/contract/zod.gen.ts'
export type { MockState } from './generated/mock-admin/contract/index.ts'
export type { MockStateStore } from './lib/stateStore.ts'
