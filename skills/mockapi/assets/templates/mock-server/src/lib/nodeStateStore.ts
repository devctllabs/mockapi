// @ts-nocheck -- mockapi template source; stripped during generation
import {
  mkdir,
  readFile,
  writeFile,
} from 'node:fs/promises'
import path from 'node:path'

import { clone } from './clone.ts'
import {
  newMswDataStateStore,
  type MswDataStateStore,
} from './stateStore.ts'
import type { MockState } from '../generated/mock-admin/contract/index.ts'
import { zMockState } from '../generated/mock-admin/contract/zod.gen.ts'
import { seedState } from '../generated/mock-admin/state/seed.ts'

export type MockStateOptions = {
  initialState?: MockState
  stateFile?: string
}

export const newFileMockStateStore = async (
  options: MockStateOptions = {},
): Promise<MswDataStateStore> => {
  const initialState = options.initialState
    ? clone(options.initialState)
    : (await readPersistedState(options.stateFile)) ?? seedState()

  return newMswDataStateStore({
    initialState,
    persist: (state) => persistState(options.stateFile, state),
  })
}

const persistState = async (stateFile: string | undefined, state: MockState) => {
  if (!stateFile) {
    return
  }

  await mkdir(path.dirname(stateFile), { recursive: true })
  await writeFile(stateFile, `${JSON.stringify(state, null, 2)}\n`, 'utf8')
}

const readPersistedState = async (stateFile: string | undefined) => {
  if (!stateFile) {
    return null
  }

  try {
    const result = zMockState.safeParse(JSON.parse(await readFile(stateFile, 'utf8')))

    return result.success ? result.data : null
  } catch (error) {
    if (isNodeFileError(error) && error.code === 'ENOENT') {
      return null
    }

    console.warn(`Ignoring invalid mock state at ${stateFile}. Resetting to seed state.`)

    return null
  }
}

const isNodeFileError = (error: unknown): error is NodeJS.ErrnoException =>
  error instanceof Error && 'code' in error
