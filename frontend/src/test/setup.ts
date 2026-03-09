import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
})

Object.defineProperty(globalThis.navigator, 'clipboard', {
  configurable: true,
  value: {
    writeText: vi.fn(),
  },
})
