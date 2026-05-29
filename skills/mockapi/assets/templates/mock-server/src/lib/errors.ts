// @ts-nocheck -- mockapi template source; stripped during generation
import { z } from 'zod'

export const zMockErrorBody = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
})

export type MockErrorBody = z.infer<typeof zMockErrorBody>

export class MockHttpError extends Error {
  readonly body: MockErrorBody
  readonly status: number

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.body = {
      error: {
        code,
        message,
      },
    }
  }
}

export const badRequest = (message: string) =>
  new MockHttpError(400, 'bad_request', message)

export const validationError = (message: string) =>
  new MockHttpError(422, 'validation_error', message)

export const notFound = (resource: string, id: string) =>
  new MockHttpError(404, 'not_found', `${resource} ${id} was not found`)

export const conflict = (message: string) =>
  new MockHttpError(409, 'conflict', message)

export const unexpected = (message = 'Unexpected mock server error') =>
  new MockHttpError(500, 'unexpected', message)
