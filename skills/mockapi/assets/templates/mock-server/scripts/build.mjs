import { rm } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { build } from 'esbuild'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const distRoot = path.join(packageRoot, 'dist')

await rm(distRoot, { recursive: true, force: true })

await build({
  bundle: true,
  entryPoints: [path.join(packageRoot, 'src/server.ts')],
  format: 'esm',
  outfile: path.join(distRoot, 'server.js'),
  platform: 'node',
  sourcemap: true,
  target: 'node20',
})
