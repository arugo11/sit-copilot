import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api/client'
import { useLiveSessionStore } from './liveSessionStore'

const mocks = vi.hoisted(() => ({
  updateLangMode: vi.fn(),
}))

vi.mock('@/lib/api/client', () => {
  class ApiError extends Error {
    status: number

    constructor(status: number, message: string) {
      super(message)
      this.status = status
      this.name = 'ApiError'
    }
  }

  return {
    ApiError,
    demoApi: {
      updateLangMode: mocks.updateLangMode,
    },
  }
})

describe('liveSessionStore hydrateFromSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useLiveSessionStore.getState().resetLiveData()
    useLiveSessionStore.getState().setPaidFeatureVisibility({
      translation: true,
      summary: true,
      keyterms: true,
      qa: true,
    })
  })

  it('hydrates assist toggles from user settings', () => {
    useLiveSessionStore.getState().hydrateFromSettings({
      assistSummaryEnabled: true,
      assistKeytermsEnabled: true,
    })

    const state = useLiveSessionStore.getState()
    expect(state.summaryEnabled).toBe(true)
    expect(state.keytermsEnabled).toBe(true)
  })

  it('keeps local language and does not reject when session is already finalized', async () => {
    useLiveSessionStore.getState().setSessionId('session-123')
    mocks.updateLangMode.mockRejectedValueOnce(new ApiError(409, 'conflict'))

    await expect(
      useLiveSessionStore.getState().switchLanguage('easy-ja')
    ).resolves.toBeUndefined()

    const state = useLiveSessionStore.getState()
    expect(state.selectedLanguage).toBe('easy-ja')
    expect(state.langMode).toBe('easy-ja')
  })
})
