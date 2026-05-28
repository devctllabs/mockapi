// @ts-nocheck -- mockapi template source; stripped during generation
import { serve } from '@hono/node-server'

import { newMockApiApp } from './app.ts'
import { readMockServerConfig } from './config.ts'
import { newMockApiControllers } from './controllers.ts'

const config = readMockServerConfig()
const app = newMockApiApp({
  controllers: newMockApiControllers({
    stateFile: config.stateFile,
  }),
})

serve(
  {
    fetch: app.fetch,
    hostname: config.hostname,
    port: config.port,
  },
  (info) => {
    console.log(`Mock API listening on http://${info.address}:${info.port}`)
    console.log(`State snapshot: ${config.stateFile}`)
  },
)
