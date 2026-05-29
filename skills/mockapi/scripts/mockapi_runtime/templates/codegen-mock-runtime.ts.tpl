{{GENERATED_HEADER}}
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  generateMockRuntimeFiles,
  type RuntimeConfig,
} from './lib/mockRuntimeCodegen.ts'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const packageRoot = path.resolve(dirname, '..')

const runtimeConfigs = [
{{RUNTIME_CONFIGS}},
] as const satisfies readonly RuntimeConfig[]

await generateMockRuntimeFiles(runtimeConfigs)
