{{GENERATED_HEADER}}
import { defineConfig } from '@hey-api/openapi-ts'

const plugins = [
  {
    name: '@hey-api/typescript',
  },
  {
    definitions: true,
    name: 'zod',
    requests: false,
    responses: true,
  },
] as const

export default defineConfig([
{{CONFIGS}},
])
