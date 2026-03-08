import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAudioInputStore } from '@/stores/audioInputStore'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { LectureLivePage } from './LectureLivePage'

const mocks = vi.hoisted(() => ({
  showToast: vi.fn(),
  announceConnection: vi.fn(),
  announceQaStatus: vi.fn(),
  startRecording: vi.fn(async () => {
    useAudioInputStore.setState({ isRecording: true })
  }),
  stopRecording: vi.fn(() => {
    useAudioInputStore.setState({ isRecording: false })
  }),
  startListening: vi.fn(),
  stopListening: vi.fn(),
  streamConnect: vi.fn(async () => {}),
  streamDisconnect: vi.fn(),
  streamSetTransport: vi.fn(),
  streamSubscribe: vi.fn((_type: string, _handler: unknown) => vi.fn()),
  finalizeDemoSession: vi.fn(async () => ({
    session_id: 'session-123',
    status: 'finalized',
  })),
  finalizeDemoSessionKeepalive: vi.fn(),
  ingestSpeechChunk: vi.fn(),
  transformSubtitle: vi.fn(),
  analyzeKeyterms: vi.fn(),
  updateLangMode: vi.fn(),
  buildIndex: vi.fn(),
}))

const reviewQaState = {
  qaTurns: [],
  status: 'idle' as const,
  submitQuestion: vi.fn(),
  applyChunk: vi.fn(),
  applyDone: vi.fn(),
  failAnswer: vi.fn(),
  retryAnswer: vi.fn(),
  reset: vi.fn(),
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      resolvedLanguage: 'ja',
      language: 'ja',
    },
  }),
}))

vi.mock('@/hooks/useLiveRegion', () => ({
  useConnectionAnnouncer: () => ({
    announceConnection: mocks.announceConnection,
  }),
  useQaAnnouncer: () => ({
    announceQaStatus: mocks.announceQaStatus,
  }),
}))

vi.mock('@/components/common/Toast', () => ({
  useToast: () => ({
    showToast: mocks.showToast,
  }),
}))

vi.mock('@/components/common/AppShell', () => ({
  AppShell: ({
    topbar,
    rightRail,
    children,
  }: {
    topbar?: ReactNode
    rightRail?: ReactNode
    children: ReactNode
  }) => (
    <div>
      <div>{topbar}</div>
      <div>{rightRail}</div>
      <div>{children}</div>
    </div>
  ),
}))

vi.mock('@/features/live/components/TranscriptPanel', () => ({
  TranscriptPanel: () => <div data-testid="transcript-panel" />,
}))

vi.mock('@/features/live/components/AssistPanel', () => ({
  AssistPanel: () => <div data-testid="assist-panel" />,
}))

vi.mock('@/features/review/reviewQaApi', () => ({
  createReviewAnswerId: () => 'qa-test',
  requestReviewQaAnswer: vi.fn(),
}))

vi.mock('@/features/review/qaResponseMapper', () => ({
  mapLectureQaResponseToChunk: vi.fn(),
  mapLectureQaResponseToDone: vi.fn(),
}))

vi.mock('@/stores/reviewQaStore', () => ({
  useReviewQaStore: (selector: (state: typeof reviewQaState) => unknown) =>
    selector(reviewQaState),
}))

vi.mock('@/lib/api/hooks', () => ({
  useUserSettings: () => ({
    data: {
      language: 'ja',
      transcriptDensity: 'comfortable',
      autoScrollDefault: true,
    },
  }),
}))

vi.mock('@/features/audio/useSpeechRecognition', () => ({
  useSpeechRecognition: () => ({
    isSupported: true,
    startListening: mocks.startListening,
    stopListening: mocks.stopListening,
  }),
}))

vi.mock('@/features/audio/useMicrophoneInput', async () => {
  const audioStore = await vi.importActual<typeof import('@/stores/audioInputStore')>(
    '@/stores/audioInputStore'
  )

  return {
    useMicrophoneInput: () => ({
      isRecording: audioStore.useAudioInputStore((state) => state.isRecording),
      audioLevel: audioStore.useAudioInputStore((state) => state.audioLevel),
      lastError: audioStore.useAudioInputStore((state) => state.lastError),
      startRecording: mocks.startRecording,
      stopRecording: mocks.stopRecording,
    }),
  }
})

vi.mock('@/lib/stream', () => ({
  sseStreamTransport: {},
  streamClient: {
    subscribe: mocks.streamSubscribe,
    setTransport: mocks.streamSetTransport,
    connect: mocks.streamConnect,
    disconnect: mocks.streamDisconnect,
  },
}))

vi.mock('@/lib/api/client', () => {
  class ApiError extends Error {
    status: number

    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  }

  return {
    ApiError,
    demoApi: {
      finalizeDemoSession: mocks.finalizeDemoSession,
      finalizeDemoSessionKeepalive: mocks.finalizeDemoSessionKeepalive,
      ingestSpeechChunk: mocks.ingestSpeechChunk,
      transformSubtitle: mocks.transformSubtitle,
      analyzeKeyterms: mocks.analyzeKeyterms,
      updateLangMode: mocks.updateLangMode,
    },
    lectureQaApi: {
      buildIndex: mocks.buildIndex,
    },
    getApiErrorMessage: () => 'request failed',
  }
})

let visibilityState: DocumentVisibilityState = 'visible'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/lectures/session-123/live']}>
      <Routes>
        <Route path="/lectures/:id/live" element={<LectureLivePage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('LectureLivePage', () => {
  beforeEach(() => {
    visibilityState = 'visible'
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => visibilityState,
    })

    useLiveSessionStore.getState().resetLiveData()
    useAudioInputStore.getState().reset()
    vi.clearAllMocks()
  })

  it('does not start microphone or SSE on initial render', () => {
    renderPage()

    expect(mocks.startRecording).not.toHaveBeenCalled()
    expect(mocks.streamConnect).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'live.stream.startRecording' })).toBeInTheDocument()
  })

  it('starts only after explicit action and finalizes when the tab becomes hidden', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: 'live.stream.startRecording' })
    )

    await waitFor(() => {
      expect(mocks.startRecording).toHaveBeenCalledTimes(1)
      expect(mocks.streamConnect).toHaveBeenCalledWith('session-123')
    })

    expect(
      await screen.findByRole('button', { name: 'lectures.actions.finalize' })
    ).toBeInTheDocument()

    await act(async () => {
      visibilityState = 'hidden'
      document.dispatchEvent(new Event('visibilitychange'))
    })

    await waitFor(() => {
      expect(mocks.finalizeDemoSession).toHaveBeenCalledWith('session-123')
      expect(mocks.streamDisconnect).toHaveBeenCalled()
    })
  })
})
