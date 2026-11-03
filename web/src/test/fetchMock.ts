import { vi } from 'vitest'

type Handler = (req: { method: string; url: URL; body: unknown }) => unknown | Promise<unknown>

/** Minimal fetch stub for RTK Query: `routes['GET /admin/users'] = () => body`. */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; search: string; auth: string | null }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init)
    const url = new URL(request.url)
    const text = await request.text()
    calls.push({
      method: request.method,
      path: url.pathname,
      search: url.search,
      auth: request.headers.get('Authorization'),
    })
    const key = `${request.method} ${url.pathname}`
    const handler =
      routes[key] ??
      Object.entries(routes).find(([pattern]) => {
        const [m, p] = pattern.split(' ')
        const re = new RegExp(`^${p.replace(/:[^/]+/g, '[^/]+')}$`)
        return m === request.method && re.test(url.pathname)
      })?.[1]
    if (!handler) return new Response(JSON.stringify({ message: 'not mocked' }), { status: 404 })
    const result = await handler({ method: request.method, url, body: text ? JSON.parse(text) : undefined })
    if (result instanceof Response) return result
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}
