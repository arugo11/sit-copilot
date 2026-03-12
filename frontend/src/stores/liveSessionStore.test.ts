import { beforeEach, describe, expect, it } from 'vitest'
import { useLiveSessionStore } from './liveSessionStore'

describe('liveSessionStore hydrateFromSettings', () => {
  beforeEach(() => {
    useLiveSessionStore.getState().resetLiveData()
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
})
