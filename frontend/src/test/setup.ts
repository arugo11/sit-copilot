import { beforeEach, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'

type Listener = (event: MediaQueryListEvent) => void

let viewportWidth = 1280
const mediaListeners = new Map<string, Set<Listener>>()

function evaluateQuery(query: string): boolean {
  const maxMatch = query.match(/max-width:\s*(\d+)px/)
  if (maxMatch) {
    return viewportWidth <= Number(maxMatch[1])
  }
  const minMatch = query.match(/min-width:\s*(\d+)px/)
  if (minMatch) {
    return viewportWidth >= Number(minMatch[1])
  }
  return false
}

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string): MediaQueryList => ({
    media: query,
    matches: evaluateQuery(query),
    onchange: null,
    addEventListener: (_event: string, listener: EventListenerOrEventListenerObject) => {
      if (typeof listener !== 'function') {
        return
      }
      const listeners = mediaListeners.get(query) ?? new Set<Listener>()
      listeners.add(listener)
      mediaListeners.set(query, listeners)
    },
    removeEventListener: (_event: string, listener: EventListenerOrEventListenerObject) => {
      if (typeof listener !== 'function') {
        return
      }
      mediaListeners.get(query)?.delete(listener)
    },
    addListener: (listener: Listener) => {
      const listeners = mediaListeners.get(query) ?? new Set<Listener>()
      listeners.add(listener)
      mediaListeners.set(query, listeners)
    },
    removeListener: (listener: Listener) => {
      mediaListeners.get(query)?.delete(listener)
    },
    dispatchEvent: () => true,
  }),
})

Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
})

window.resizeTo = (width: number, height: number) => {
  viewportWidth = width
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: height })
  window.dispatchEvent(new Event('resize'))

  mediaListeners.forEach((listeners, query) => {
    const event = { matches: evaluateQuery(query), media: query } as MediaQueryListEvent
    listeners.forEach((listener) => listener(event))
  })
}

beforeEach(() => {
  window.resizeTo(1280, 800)
})
