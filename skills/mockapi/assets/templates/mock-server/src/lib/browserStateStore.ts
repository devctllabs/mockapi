// @ts-nocheck -- mockapi template source; stripped during generation
import { clone } from './clone.ts'
import {
  newMswDataStateStore,
  type MswDataStateStore,
} from './stateStore.ts'
import type { MockState } from '../generated/mock-admin/contract/index.ts'
import { zMockState } from '../generated/mock-admin/contract/zod.gen.ts'
import { seedState } from '../generated/mock-admin/state/seed.ts'

export type BrowserMockStateStoreOptions = {
  initialState?: MockState
  storageKey: string
}

export const newBrowserMockStateStore = async (
  options: BrowserMockStateStoreOptions,
): Promise<MswDataStateStore> => {
  const initialState = options.initialState
    ? clone(options.initialState)
    : readPersistedState(options.storageKey) ?? seedState()

  return newMswDataStateStore({
    initialState,
    persist: (state) => persistState(options.storageKey, state),
  })
}

const persistState = (storageKey: string, state: MockState) => {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(storageKey, JSON.stringify(state))
}

const readPersistedState = (storageKey: string) => {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(storageKey)

  if (!raw) {
    return null
  }

  try {
    const result = zMockState.safeParse(JSON.parse(raw))

    return result.success ? result.data : null
  } catch {
    return null
  }
}
