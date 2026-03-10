import { render, screen } from '@testing-library/react'
import type { AnchorHTMLAttributes, ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { LectureLivePage } from './LectureLivePage'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options?.sessionId ? `${key}:${options.sessionId}` : key,
    i18n: {
      language: 'ja',
      resolvedLanguage: 'ja',
    },
  }),
}))

vi.mock('react-router-dom', () => ({
  Link: ({ children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a {...props}>{children}</a>
  ),
  useNavigate: () => vi.fn(),
  useParams: () => ({ id: 'session-12345678' }),
}))

vi.mock('@/hooks', () => ({
  useIsMobile: () => true,
}))

vi.mock('@/hooks/useLiveRegion', () => ({
  useConnectionAnnouncer: () => ({ announceConnection: vi.fn() }),
  useQaAnnouncer: () => ({ announceQaStatus: vi.fn() }),
}))

vi.mock('@/components/common/Toast', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))

vi.mock('@/components/common/AppShell', () => ({
  AppShell: ({
    topbar,
    children,
    rightRail,
  }: {
    topbar?: ReactNode
    children: ReactNode
    rightRail?: ReactNode
  }) => (
    <div>
      <div>{topbar}</div>
      <div>{children}</div>
      <div>{rightRail}</div>
    </div>
  ),
}))

vi.mock('@/features/live/components/TranscriptPanel', () => ({
  TranscriptPanel: () => <div data-testid="transcript-panel">Transcript Panel</div>,
}))

vi.mock('@/features/live/components/AssistPanel', () => ({
  AssistPanel: () => <div data-testid="assist-panel">Assist Panel</div>,
}))

vi.mock('@/features/review/reviewQaApi', () => ({
  createReviewAnswerId: () => 'answer-1',
  requestReviewQaAnswer: vi.fn(),
}))

vi.mock('@/features/review/qaResponseMapper', () => ({
  mapLectureQaResponseToChunk: vi.fn(),
  mapLectureQaResponseToDone: vi.fn(),
}))

vi.mock('@/lib/stream', () => ({
  sseStreamTransport: {},
  streamClient: {
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn(),
    subscribe: vi.fn(() => () => undefined),
    setTransport: vi.fn(),
  },
}))

vi.mock('@/stores/audioInputStore', () => ({
  useAudioInputStore: (selector: (state: {
    isRecording: boolean
    audioLevel: number
  }) => unknown) => selector({
    isRecording: false,
    audioLevel: 0.25,
  }),
}))

vi.mock('@/stores/liveSessionStore', () => {
  const state = {
    connection: 'live',
    liveState: 'idle',
    paidFeatureVisibility: {
      translation: true,
      summary: true,
      keyterms: true,
      qa: true,
    },
    transcriptLagMs: 0,
    transcriptLines: [],
    selectedLanguage: 'ja',
    langMode: 'ja',
    sessionId: 'session-12345678',
    summaryPoints: [],
    assistTerms: [],
    summaryEnabled: true,
    keytermsEnabled: true,
    translationFallbackActive: false,
    autoScroll: true,
    transcriptDensity: 'comfortable',
    sourceFrames: [],
    ocrChunks: [],
    setConnection: vi.fn(),
    setLiveState: vi.fn(),
    setSessionId: vi.fn(),
    applyTranscriptPartial: vi.fn(),
    applyTranscriptFinal: vi.fn(),
    replaceTranscriptLineText: vi.fn(),
    setTranscriptCorrectionStatus: vi.fn(),
    applyTranslationFinal: vi.fn(),
    pushSourceFrame: vi.fn(),
    pushSourceOcr: vi.fn(),
    appendAssistTerms: vi.fn(),
    setTranslationFallbackActive: vi.fn(),
    hydrateFromSettings: vi.fn(),
    resetLiveData: vi.fn(),
    switchLanguage: vi.fn().mockResolvedValue(undefined),
    setAssistSummary: vi.fn(),
    setAssistTerms: vi.fn(),
    setSummaryEnabled: vi.fn(),
    setKeytermsEnabled: vi.fn(),
    setAutoScroll: vi.fn(),
    setTranscriptDensity: vi.fn(),
  }
  const useLiveSessionStore = Object.assign(
    (selector: (value: typeof state) => unknown) => selector(state),
    {
      getState: () => state,
    }
  )
  return {
    useLiveSessionStore,
  }
})

vi.mock('@/stores/reviewQaStore', () => ({
  useReviewQaStore: (selector: (state: {
    qaTurns: never[]
    status: 'idle'
    submitQuestion: ReturnType<typeof vi.fn>
    applyChunk: ReturnType<typeof vi.fn>
    applyDone: ReturnType<typeof vi.fn>
    failAnswer: ReturnType<typeof vi.fn>
    retryAnswer: ReturnType<typeof vi.fn>
    reset: ReturnType<typeof vi.fn>
  }) => unknown) =>
    selector({
      qaTurns: [],
      status: 'idle',
      submitQuestion: vi.fn(),
      applyChunk: vi.fn(),
      applyDone: vi.fn(),
      failAnswer: vi.fn(),
      retryAnswer: vi.fn(),
      reset: vi.fn(),
    }),
}))

vi.mock('@/features/audio/useMicrophoneInput', () => ({
  useMicrophoneInput: () => ({
    isRecording: false,
    audioLevel: 0.25,
    lastError: null,
    startRecording: vi.fn().mockResolvedValue(undefined),
    stopRecording: vi.fn(),
  }),
}))

vi.mock('@/features/audio/useSpeechRecognition', () => ({
  useSpeechRecognition: () => ({
    isSupported: false,
    startListening: vi.fn(),
    stopListening: vi.fn(),
  }),
}))

vi.mock('@/lib/api/hooks', () => ({
  useUserSettings: () => ({ data: undefined }),
}))

vi.mock('@/lib/api/client', () => ({
  ApiError: class extends Error {
    status = 500
  },
  demoApi: {
    ingestSpeechChunk: vi.fn(),
    auditAndApplySpeechChunk: vi.fn(),
    analyzeKeyterms: vi.fn(),
    transformSubtitle: vi.fn(),
    getLatestSummary: vi.fn(),
  },
  lectureQaApi: {
    buildIndex: vi.fn().mockResolvedValue(undefined),
  },
  getApiErrorMessage: () => 'error',
}))

vi.mock('@/features/live/utils/assistSupport', () => ({
  mapSummaryKeyTermsToAssistTerms: vi.fn(() => []),
}))

describe('LectureLivePage responsive layout', () => {
  it('renders mobile tab navigation for transcript and assist', () => {
    render(<LectureLivePage />)

    expect(screen.getByRole('tab', { name: 'live.stream.title' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'assistPanel.sections.qa' })).toBeInTheDocument()
    expect(screen.getByTestId('transcript-panel')).toBeInTheDocument()
  })
})
