// @ts-nocheck -- mockapi template source; stripped during generation
export type MockRequestContext = {
  headers: Headers
  request: Request
  responseHeaders: Headers
}

export const newMockRequestContext = (request: Request): MockRequestContext => ({
  headers: request.headers,
  request,
  responseHeaders: new Headers(),
})
