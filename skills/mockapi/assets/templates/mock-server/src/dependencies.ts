// @ts-nocheck -- mockapi template source; stripped during generation
import type { MockStateStore } from './lib/stateStore.ts'

export type MockApiDependencies = {
  stateStore: MockStateStore
}

export const newMockApiDependencies = (
  stateStore: MockStateStore,
): MockApiDependencies => ({
  stateStore,
})
