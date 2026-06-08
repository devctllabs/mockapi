{{STARTER_HEADER}}
import { Hono } from 'hono'
import { cors } from 'hono/cors'

import {
  newMemoryMockApiControllers,
  type MockApiControllers,
} from './controllers.ts'
{{RUNTIME_IMPORTS}}
import { notFound } from './lib/errors.ts'
import {
  mockJsonResponse,
  registerGeneratedMockRoutes,
} from './lib/honoMockRuntime.ts'

export type NewMockApiAppOptions = {
  basePath?: string
  controllers?: MockApiControllers
}

export const newMockApiApp = async ({
  basePath = {{DEFAULT_BASE_PATH}},
  controllers,
}: NewMockApiAppOptions = {}) => {
  const app = new Hono()
  const mockControllers = controllers ?? await newMemoryMockApiControllers()

  app.use('*', cors())
{{ROUTE_REGISTRATIONS}}

  app.notFound(() => {
    const routeError = notFound('route', 'request')

    return mockJsonResponse(routeError.body, routeError.status)
  })

  return app
}
