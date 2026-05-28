// @ts-nocheck -- mockapi template source; stripped during generation
import type { Hono } from 'hono'
import type { z } from 'zod'

import { badRequest, MockHttpError, unexpected } from './errors.ts'
import { newMockRequestContext, type MockRequestContext } from './requestContext.ts'

type RuntimeRoute = {
  method: 'DELETE' | 'GET' | 'PATCH' | 'POST' | 'PUT'
  operationId: string
  path: string
  requestBody: boolean
}

type Runtime = {
  generatedErrorResponseSchemas: Partial<Record<string, Partial<Record<string, z.ZodType>>>>
  generatedOperationHandlers: Record<
    string,
    (request: never) => Promise<{ body?: unknown; status: number }>
  >
  generatedRequestBodySchemas: Partial<Record<string, z.ZodType>>
  generatedResponseSchemas: Record<string, z.ZodType>
  generatedRouteDefinitions: readonly RuntimeRoute[]
}

const methods = {
  DELETE: 'delete',
  GET: 'get',
  PATCH: 'patch',
  POST: 'post',
  PUT: 'put',
} as const

export const mockJsonResponse = (body: unknown, status: number, headers?: Headers) =>
  new Response(JSON.stringify(body), {
    headers: {
      'content-type': 'application/json',
      ...(headers ? Object.fromEntries(headers.entries()) : {}),
    },
    status,
  })

const parseBody = async (
  request: Request,
  route: RuntimeRoute,
  schema: z.ZodType | undefined,
) => {
  if (!route.requestBody) {
    return undefined
  }

  const rawBody = await request.json().catch(() => {
    throw badRequest('Request body must be valid JSON.')
  })

  return schema ? schema.parse(rawBody) : rawBody
}

export const registerGeneratedMockRoutes = (
  app: Hono,
  options: {
    basePath?: string
    controllers: Record<string, unknown>
    runtime: Runtime
  },
) => {
  for (const route of options.runtime.generatedRouteDefinitions) {
    const method = methods[route.method]
    const routePath = `${options.basePath ?? ''}${route.path}`

    app[method](routePath, async (context) => {
      const requestContext = newMockRequestContext(context.req.raw)

      try {
        const body = await parseBody(
          context.req.raw,
          route,
          options.runtime.generatedRequestBodySchemas[route.operationId],
        )
        const result = await options.runtime.generatedOperationHandlers[route.operationId]({
          context: requestContext,
          controllers: options.controllers,
          input: {
            body,
            path: context.req.param(),
            query: context.req.query(),
          },
        } as never)
        const responseSchema = options.runtime.generatedResponseSchemas[route.operationId]
        const responseBody =
          result.body === undefined ? undefined : responseSchema.parse(result.body)

        if (responseBody === undefined) {
          return new Response(null, {
            headers: requestContext.responseHeaders,
            status: result.status,
          })
        }

        return mockJsonResponse(responseBody, result.status, requestContext.responseHeaders)
      } catch (caught) {
        const error =
          caught instanceof MockHttpError
            ? caught
            : caught instanceof Error
              ? unexpected(caught.message)
              : unexpected()

        return mockJsonResponse(error.body, error.status, requestContext.responseHeaders)
      }
    })
  }
}
