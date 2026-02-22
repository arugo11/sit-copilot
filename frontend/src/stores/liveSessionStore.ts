import { create } from 'zustand'
import { demoApi } from '@/lib/api/client'
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
  sessionId: string | null
  langMode: 'ja' | 'easy-ja' | 'en'
  setConnection: (connection: ConnectionState) => void
  setAutoScroll: (autoScroll: boolean) => void
  setCameraEnabled: (enabled: boolean) => void
  setSelectedLanguage: (lang: 'ja' | 'easy-ja' | 'en') => void
  setTranscriptDensity: (density: TranscriptDensity) => void
  setLeftPanelMode: (mode: LeftPanelMode) => void
  setSessionId: (sessionId: string | null) => void
  setLangMode: (langMode: 'ja' | 'easy-ja' | 'en') => Promise<void>
  switchLanguage: (langMode: 'ja' | 'easy-ja' | 'en') => Promise<void>
  applyTranscriptPartial: (line: TranscriptLine) => void
  applyTranscriptFinal: (line: TranscriptLine) => void
  replaceTranscriptLineText: (lineId: string, correctedText: string) => void
  setTranscriptCorrectionStatus: (
    lineId: string,
    status: 'pending' | 'reviewed' | 'review_failed'
  ) => void
  applyTranslationFinal: (
    lineId: string,
    translatedText: string,
    translatedLangMode: 'easy-ja' | 'en'
  ) => void
  pushSourceFrame: (frame: SourceFrame) => void
  pushSourceOcr: (ocr: SourceOcrChunk) => void
  setAssistSummary: (summary: AssistSummaryPayload) => void
  setAssistTerms: (terms: AssistTermPayload[]) => void
  summaryEnabled: boolean
  keytermsEnabled: boolean
  toggleSummary: () => void
  toggleKeyterms: () => void
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
  | 'sessionId'
  | 'langMode'
  | 'summaryEnabled'
  | 'keytermsEnabled'
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
  sessionId: null,
  langMode: 'ja',
  summaryEnabled: false,
  keytermsEnabled: false,
}

export const useLiveSessionStore = create<LiveSessionStore>((set, get) => ({
  ...initialState,

  setConnection: (connection) => set({ connection }),
  setAutoScroll: (autoScroll) => set({ autoScroll }),
  setCameraEnabled: (cameraEnabled) => set({ cameraEnabled }),
  setSelectedLanguage: (selectedLanguage) => set({ selectedLanguage }),
  setTranscriptDensity: (transcriptDensity) => set({ transcriptDensity }),
  setLeftPanelMode: (leftPanelMode) => set({ leftPanelMode }),
  setSessionId: (sessionId) => set({ sessionId }),

  setLangMode: async (langMode) => {
    const { sessionId } = get()
    if (!sessionId) {
      console.warn('Cannot update lang_mode: no active session')
      return
    }
    const previousLangMode = get().langMode
    set({ langMode })
    try {
      await demoApi.updateLangMode({ session_id: sessionId, lang_mode: langMode })
    } catch (error) {
      set({ langMode: previousLangMode })
      throw error
    }
  },

  switchLanguage: async (langMode) => {
    const { sessionId, selectedLanguage, langMode: previousLangMode } = get()
    set({ selectedLanguage: langMode, langMode })

    if (!sessionId) {
      return
    }

    try {
      await demoApi.updateLangMode({ session_id: sessionId, lang_mode: langMode })
    } catch (error) {
      set({ selectedLanguage, langMode: previousLangMode })
      throw error
    }
  },

  applyTranscriptPartial: (line) =>
    set((state) => {
      const existing = state.transcriptLines.find((item) => item.id === line.id)
      const mergedLine = {
        ...existing,
        ...line,
        originalLangText:
          line.originalLangText ?? existing?.originalLangText ?? line.sourceLangText,
      }
      const without = state.transcriptLines.filter((item) => item.id !== line.id)
      return {
        transcriptLines: [...without, mergedLine].sort((a, b) => a.tsStartMs - b.tsStartMs),
        transcriptLagMs: Math.max(400, state.transcriptLagMs),
      }
    }),

  applyTranscriptFinal: (line) =>
    set((state) => {
      const existing = state.transcriptLines.find((item) => item.id === line.id)
      const mergedLine = {
        ...existing,
        ...line,
        originalLangText:
          line.originalLangText ?? existing?.originalLangText ?? line.sourceLangText,
      }
      const without = state.transcriptLines.filter((item) => item.id !== line.id)
      return {
        transcriptLines: [...without, mergedLine].sort((a, b) => a.tsStartMs - b.tsStartMs),
        transcriptLagMs: 120,
      }
    }),

  replaceTranscriptLineText: (lineId, correctedText) =>
    set((state) => {
      const normalized = correctedText.trim()
      if (!normalized) {
        return state
      }

      let changed = false
      const updated = state.transcriptLines.map((line) => {
        if (line.id !== lineId) {
          return line
        }
        if (line.sourceLangText === normalized) {
          return line
        }
        changed = true
        return {
          ...line,
          originalLangText: line.originalLangText ?? line.sourceLangText,
          sourceLangText: normalized,
        }
      })

      if (!changed) {
        return state
      }

      return {
        transcriptLines: updated,
        transcriptLagMs: 100,
      }
    }),

  setTranscriptCorrectionStatus: (lineId, status) =>
    set((state) => {
      let changed = false
      const updatedLines = state.transcriptLines.map((line) => {
        if (line.id !== lineId) {
          return line
        }
        if (line.correctionStatus === status) {
          return line
        }
        changed = true
        return { ...line, correctionStatus: status }
      })

      if (!changed) {
        return state
      }

      return { transcriptLines: updatedLines }
    }),

  applyTranslationFinal: (lineId, translatedText, translatedLangMode) =>
    set((state) => {
      let changed = false
      const updatedLines = state.transcriptLines.map((line) => {
        if (line.id !== lineId) {
          return line
        }

        if (
          line.translatedText === translatedText &&
          line.translatedLangMode === translatedLangMode
        ) {
          return line
        }

        changed = true
        return { ...line, translatedText, translatedLangMode }
      })

      if (!changed) {
        return state
      }

      return {
        transcriptLines: updatedLines,
        translationLagMs: 180,
      }
    }),

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

  toggleSummary: () => set((state) => ({ summaryEnabled: !state.summaryEnabled })),
  toggleKeyterms: () => set((state) => ({ keytermsEnabled: !state.keytermsEnabled })),

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
      sessionId: null,
      langMode: 'ja',
    }),
}))
