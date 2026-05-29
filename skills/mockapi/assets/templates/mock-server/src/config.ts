// @ts-nocheck -- mockapi template source; stripped during generation
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export type MockServerConfig = {
  hostname: string
  port: number
  stateFile: string
}

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaultStateFile = path.join(packageRoot, '.mockapi-runtime', 'db.json')

const numberFromEnv = (value: string | undefined, fallback: number) => {
  if (!value) {
    return fallback
  }

  const parsed = Number.parseInt(value, 10)

  return Number.isFinite(parsed) ? parsed : fallback
}

const resolveStateFile = (value: string | undefined) => {
  if (!value) {
    return defaultStateFile
  }

  return path.isAbsolute(value) ? value : path.resolve(packageRoot, value)
}

export const readMockServerConfig = (): MockServerConfig => ({
  hostname: process.env.MOCK_API_HOST ?? '127.0.0.1',
  port: numberFromEnv(process.env.MOCK_API_PORT, 4010),
  stateFile: resolveStateFile(process.env.MOCK_API_STATE_FILE),
})
