import { create } from 'zustand'
import { demoApi } from '@/lib/api/client'
import {
  LIVE_FEATURE_FLAGS,
  sanitizeSelectableLanguage,
} from '@/lib/featureFlags'
import type {
  AssistSummaryPayload,
  AssistTermPayload,
  ConnectionState,
  LeftPanelMode,
  LiveLifecycleState,
  LiveUiState,
  SourceFrame,
  SourceOcrChunk,
  TranscriptDensity,
  TranscriptLine,
} from '@/lib/stream'

const MAX_HISTORY = 10
const MAX_ASSIST_TERMS = 20

const defaultPaidFeatureVisibility = {
  translation: LIVE_FEATURE_FLAGS.translation,
  summary: LIVE_FEATURE_FLAGS.summary,
  keyterms: LIVE_FEATURE_FLAGS.keyterms,
  qa: LIVE_FEATURE_FLAGS.qa,
} as const

function normalizeAssistTermKey(term: string): string {
  return term.replace(/[\s\u3000]+/g, '').trim().toLowerCase()
}

function areStringArraysEqual(
  left: readonly string[],
  right: readonly string[]
): boolean {
  if (left.length !== right.length) {
    return false
  }

  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) {
      return false
    }
  }
  return true
}

function assignSubtitleSerials(lines: TranscriptLine[]): TranscriptLine[] {
  let serial = 0
  return lines.map((line) => {
    if (line.isPartial) {
      return line
    }

    serial += 1
    if (line.subtitleSerial === serial) {
      return line
    }

    return {
      ...line,
      subtitleSerial: serial,
    }
  })
}

interface LiveSessionStore extends LiveUiState {
  cameraEnabled: boolean
  sourceFrames: SourceFrame[]
  ocrChunks: SourceOcrChunk[]
  transcriptLines: TranscriptLine[]
  summaryPoints: string[]
  assistTerms: AssistTermPayload[]
  sessionId: string | null
  langMode: 'ja' | 'easy-ja' | 'en'
  translationFallbackActive: boolean
  paidFeatureVisibility: {
    translation: boolean
    summary: boolean
    keyterms: boolean
    qa: boolean
  }
  setConnection: (connection: ConnectionState) => void
  setLiveState: (liveState: LiveLifecycleState) => void
  setAutoScroll: (autoScroll: boolean) => void
  setCameraEnabled: (enabled: boolean) => void
  setSelectedLanguage: (lang: 'ja' | 'easy-ja' | 'en') => void
  setTranscriptDensity: (density: TranscriptDensity) => void
  setLeftPanelMode: (mode: LeftPanelMode) => void
  setSessionId: (sessionId: string | null) => void
  setPaidFeatureVisibility: (visibility: LiveSessionStore['paidFeatureVisibility']) => void
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
    translatedLangMode: 'easy-ja' | 'en',
    translationStatus?: 'translated' | 'fallback' | 'passthrough'
  ) => void
  pushSourceFrame: (frame: SourceFrame) => void
  pushSourceOcr: (ocr: SourceOcrChunk) => void
  setAssistSummary: (summary: AssistSummaryPayload) => void
  setAssistTerms: (terms: AssistTermPayload[]) => void
  appendAssistTerms: (terms: AssistTermPayload[]) => void
  setTranslationFallbackActive: (active: boolean) => void
  summaryEnabled: boolean
  keytermsEnabled: boolean
  setSummaryEnabled: (enabled: boolean) => void
  setKeytermsEnabled: (enabled: boolean) => void
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
  | 'liveState'
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
  | 'translationFallbackActive'
  | 'paidFeatureVisibility'
  | 'summaryEnabled'
  | 'keytermsEnabled'
> = {
  connection: 'idle',
  liveState: 'idle',
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
  translationFallbackActive: false,
  paidFeatureVisibility: { ...defaultPaidFeatureVisibility },
  summaryEnabled: false,
  keytermsEnabled: false,
}

export const useLiveSessionStore = create<LiveSessionStore>((set, get) => ({
  ...initialState,

  setConnection: (connection) => set({ connection }),
  setLiveState: (liveState) => set({ liveState }),
  setAutoScroll: (autoScroll) => set({ autoScroll }),
  setCameraEnabled: (cameraEnabled) => set({ cameraEnabled }),
  setSelectedLanguage: (selectedLanguage) =>
    set({ selectedLanguage: sanitizeSelectableLanguage(selectedLanguage) }),
  setTranscriptDensity: (transcriptDensity) => set({ transcriptDensity }),
  setLeftPanelMode: (leftPanelMode) => set({ leftPanelMode }),
  setSessionId: (sessionId) => set({ sessionId }),
  setPaidFeatureVisibility: (paidFeatureVisibility) => set({ paidFeatureVisibility }),
  setTranslationFallbackActive: (translationFallbackActive) =>
    set({ translationFallbackActive }),

  setLangMode: async (langMode) => {
    const { sessionId } = get()
    if (!sessionId) {
      console.warn('Cannot update lang_mode: no active session')
      return
    }
    const nextLangMode = sanitizeSelectableLanguage(langMode)
    const previousLangMode = get().langMode
    set({ langMode: nextLangMode })
    try {
      await demoApi.updateLangMode({
        session_id: sessionId,
        lang_mode: nextLangMode,
      })
    } catch (error) {
      set({ langMode: previousLangMode })
      throw error
    }
  },

  switchLanguage: async (langMode) => {
    const { sessionId, selectedLanguage, langMode: previousLangMode } = get()
    const nextLangMode = sanitizeSelectableLanguage(langMode)
    set({
      selectedLanguage: nextLangMode,
      langMode: nextLangMode,
      translationFallbackActive: false,
    })

    if (!sessionId) {
      return
    }

    try {
      await demoApi.updateLangMode({
        session_id: sessionId,
        lang_mode: nextLangMode,
      })
    } catch (error) {
      // 表示言語の切替はローカル機能として維持し、
      // サーバー側の lang_mode 更新だけを元に戻す。
      set({ langMode: previousLangMode })
      console.warn('Failed to persist lang_mode; keeping local language view.', {
        error,
        sessionId,
        selectedLanguage,
        requestedLangMode: nextLangMode,
      })
      throw error
    }
  },

  applyTranscriptPartial: (line) =>
    set((state) => {
      const existing = state.transcriptLines.find((item) => item.id === line.id)
      const mergedLine = {
        ...existing,
        ...line,
        // Preserve existing translation data — SSE payloads don't include
        // translatedText/translatedLangMode, so the spread above would
        // leave them intact only if the incoming object lacks those keys
        // entirely. Explicitly prioritising existing values makes this safe
        // regardless of payload shape.
        translatedText: existing?.translatedText ?? line.translatedText,
        translatedLangMode: existing?.translatedLangMode ?? line.translatedLangMode,
        translationStatus: existing?.translationStatus ?? line.translationStatus,
        subtitleSerial: existing?.subtitleSerial,
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
        // Preserve existing translation — see applyTranscriptPartial comment.
        translatedText: existing?.translatedText ?? line.translatedText,
        translatedLangMode: existing?.translatedLangMode ?? line.translatedLangMode,
        translationStatus: existing?.translationStatus ?? line.translationStatus,
        subtitleSerial: existing?.subtitleSerial,
        originalLangText:
          line.originalLangText ?? existing?.originalLangText ?? line.sourceLangText,
      }
      const without = state.transcriptLines.filter((item) => item.id !== line.id)
      const sortedLines = [...without, mergedLine].sort(
        (a, b) => a.tsStartMs - b.tsStartMs
      )
      return {
        transcriptLines: assignSubtitleSerials(sortedLines),
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

  applyTranslationFinal: (
    lineId,
    translatedText,
    translatedLangMode,
    translationStatus = 'translated'
  ) =>
    set((state) => {
      let changed = false
      const updatedLines = state.transcriptLines.map((line) => {
        if (line.id !== lineId) {
          return line
        }

        if (
          line.translatedText === translatedText &&
          line.translatedLangMode === translatedLangMode &&
          line.translationStatus === translationStatus
        ) {
          return line
        }

        changed = true
        return {
          ...line,
          translatedText,
          translatedLangMode,
          translationStatus,
        }
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
    set((state) => {
      const nextPoints = summary.points.slice(0, 3)
      if (areStringArraysEqual(state.summaryPoints, nextPoints)) {
        return state
      }
      return { summaryPoints: nextPoints }
    }),

  setAssistTerms: (assistTerms) =>
    set({ assistTerms: assistTerms.slice(0, MAX_ASSIST_TERMS) }),

  appendAssistTerms: (incomingTerms) =>
    set((state) => {
      if (!incomingTerms.length) {
        return state
      }

      const merged = [...state.assistTerms]
      const existingKeys = new Set(
        merged.map((item) => normalizeAssistTermKey(item.term))
      )

      for (const term of incomingTerms) {
        const key = normalizeAssistTermKey(term.term)
        if (!key || existingKeys.has(key)) {
          continue
        }
        merged.push(term)
        existingKeys.add(key)
      }

      return {
        assistTerms: merged.slice(0, MAX_ASSIST_TERMS),
      }
    }),

  setSummaryEnabled: (summaryEnabled) =>
    set((state) => ({
      summaryEnabled: state.paidFeatureVisibility.summary && summaryEnabled,
    })),
  setKeytermsEnabled: (keytermsEnabled) =>
    set((state) => ({
      keytermsEnabled: state.paidFeatureVisibility.keyterms && keytermsEnabled,
    })),

  toggleSummary: () =>
    set((state) => ({
      summaryEnabled:
        state.paidFeatureVisibility.summary && !state.summaryEnabled,
    })),
  toggleKeyterms: () =>
    set((state) => ({
      keytermsEnabled:
        state.paidFeatureVisibility.keyterms && !state.keytermsEnabled,
    })),

  hydrateFromSettings: (settings) =>
    set((state) => {
      // Only hydrate language if both selectedLanguage and langMode are still
      // at their default ('ja'). If the user has already switched language
      // during the live session, don't override it with persisted settings.
      const userHasSwitched =
        state.selectedLanguage !== 'ja' || state.langMode !== 'ja'
      const hydratedLang = sanitizeSelectableLanguage(
        settings.language ?? state.selectedLanguage
      )
      return {
        selectedLanguage: userHasSwitched ? state.selectedLanguage : hydratedLang,
        langMode: userHasSwitched ? state.langMode : hydratedLang,
        transcriptDensity: settings.transcriptDensity ?? state.transcriptDensity,
        autoScroll: settings.autoScrollDefault ?? state.autoScroll,
      }
    }),

  resetLiveData: () =>
    set({
      ...initialState,
      selectedLanguage: 'ja',
      transcriptDensity: 'comfortable',
      autoScroll: true,
      cameraEnabled: false,
      sessionId: null,
      liveState: 'idle',
      connection: 'idle',
      langMode: 'ja',
      translationFallbackActive: false,
      paidFeatureVisibility: { ...defaultPaidFeatureVisibility },
    }),
}))
