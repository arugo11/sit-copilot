import { create } from 'zustand'
import type {
  AssistSummaryPayload,
  AssistTermPayload,
  ConnectionState,
  LeftPanelMode,
  LiveUiState,
  SourceFrame,
  SourceOcrChunk,
  TranscriptDensity,
  TranscriptLine,
} from '@/lib/stream'

const MAX_HISTORY = 10

interface LiveSessionStore extends LiveUiState {
  cameraEnabled: boolean
  sourceFrames: SourceFrame[]
  ocrChunks: SourceOcrChunk[]
  transcriptLines: TranscriptLine[]
  summaryPoints: string[]
  assistTerms: AssistTermPayload[]
  setConnection: (connection: ConnectionState) => void
  setAutoScroll: (autoScroll: boolean) => void
  setCameraEnabled: (enabled: boolean) => void
  setSelectedLanguage: (lang: 'ja' | 'en') => void
  setTranscriptDensity: (density: TranscriptDensity) => void
  setLeftPanelMode: (mode: LeftPanelMode) => void
  applyTranscriptPartial: (line: TranscriptLine) => void
  applyTranscriptFinal: (line: TranscriptLine) => void
  applyTranslationFinal: (lineId: string, translatedText: string) => void
  pushSourceFrame: (frame: SourceFrame) => void
  pushSourceOcr: (ocr: SourceOcrChunk) => void
  setAssistSummary: (summary: AssistSummaryPayload) => void
  setAssistTerms: (terms: AssistTermPayload[]) => void
  hydrateFromSettings: (settings: {
    language?: 'ja' | 'en'
    transcriptDensity?: TranscriptDensity
    autoScrollDefault?: boolean
  }) => void
  resetLiveData: () => void
}

const initialState: Pick<
  LiveSessionStore,
  | 'connection'
  | 'transcriptLagMs'
  | 'translationLagMs'
  | 'sourceLagMs'
  | 'autoScroll'
  | 'cameraEnabled'
  | 'selectedLanguage'
  | 'transcriptDensity'
  | 'leftPanelMode'
  | 'sourceFrames'
  | 'ocrChunks'
  | 'transcriptLines'
  | 'summaryPoints'
  | 'assistTerms'
> = {
  connection: 'connecting',
  transcriptLagMs: 0,
  translationLagMs: 0,
  sourceLagMs: 0,
  autoScroll: true,
  cameraEnabled: false,
  selectedLanguage: 'ja',
  transcriptDensity: 'comfortable',
  leftPanelMode: 'slides',
  sourceFrames: [],
  ocrChunks: [],
  transcriptLines: [],
  summaryPoints: [],
  assistTerms: [],
}

export const useLiveSessionStore = create<LiveSessionStore>((set) => ({
  ...initialState,

  setConnection: (connection) => set({ connection }),
  setAutoScroll: (autoScroll) => set({ autoScroll }),
  setCameraEnabled: (cameraEnabled) => set({ cameraEnabled }),
  setSelectedLanguage: (selectedLanguage) => set({ selectedLanguage }),
  setTranscriptDensity: (transcriptDensity) => set({ transcriptDensity }),
  setLeftPanelMode: (leftPanelMode) => set({ leftPanelMode }),

  applyTranscriptPartial: (line) =>
    set((state) => {
      const without = state.transcriptLines.filter((item) => item.id !== line.id)
      return {
        transcriptLines: [...without, line].sort((a, b) => a.tsStartMs - b.tsStartMs),
        transcriptLagMs: Math.max(400, state.transcriptLagMs),
      }
    }),

  applyTranscriptFinal: (line) =>
    set((state) => {
      const without = state.transcriptLines.filter((item) => item.id !== line.id)
      return {
        transcriptLines: [...without, line].sort((a, b) => a.tsStartMs - b.tsStartMs),
        transcriptLagMs: 120,
      }
    }),

  applyTranslationFinal: (lineId, translatedText) =>
    set((state) => ({
      transcriptLines: state.transcriptLines.map((line) =>
        line.id === lineId ? { ...line, translatedText } : line
      ),
      translationLagMs: 180,
    })),

  pushSourceFrame: (frame) =>
    set((state) => ({
      sourceFrames: [frame, ...state.sourceFrames].slice(0, MAX_HISTORY),
      sourceLagMs: 300,
    })),

  pushSourceOcr: (ocr) =>
    set((state) => ({
      ocrChunks: [ocr, ...state.ocrChunks].slice(0, MAX_HISTORY),
      sourceLagMs: 260,
    })),

  setAssistSummary: (summary) =>
    set({ summaryPoints: summary.points.slice(0, 3) }),

  setAssistTerms: (assistTerms) => set({ assistTerms: assistTerms.slice(0, 4) }),

  hydrateFromSettings: (settings) =>
    set((state) => ({
      selectedLanguage: settings.language ?? state.selectedLanguage,
      transcriptDensity: settings.transcriptDensity ?? state.transcriptDensity,
      autoScroll: settings.autoScrollDefault ?? state.autoScroll,
    })),

  resetLiveData: () =>
    set({
      ...initialState,
      selectedLanguage: 'ja',
      transcriptDensity: 'comfortable',
      autoScroll: true,
      cameraEnabled: false,
    }),
}))
