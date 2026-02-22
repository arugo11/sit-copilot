export type ConnectionState =
  | 'connecting'
  | 'live'
  | 'reconnecting'
  | 'degraded'
  | 'error'

export type TranscriptDensity = 'comfortable' | 'compact'
export type LeftPanelMode = 'slides' | 'board' | 'split'

export interface TranscriptLine {
  id: string
  tsStartMs: number
  tsEndMs: number
  speakerLabel?: string
  sourceLangText: string
  originalLangText?: string
  translatedText?: string
  translatedLangMode?: 'easy-ja' | 'en'
  correctionStatus?: 'pending' | 'reviewed' | 'review_failed'
  confidence?: number
  isPartial: boolean
  sourceRefs: {
    audioSegmentId: string
    sourceFrameIds?: string[]
  }
}

export interface SourceFrame {
  id: string
  source: 'slide' | 'board'
  timestampMs: number
  thumbnailUrl: string
  ocrExcerpt: string
}

export interface SourceOcrChunk {
  frameId: string
  source: 'slide' | 'board'
  timestampMs: number
  text: string
}

export interface AssistSummaryPayload {
  timestampMs: number
  points: string[]
}

export interface AssistTermPayload {
  term: string
  explanation: string
  translation: string
}

export interface QaAnswerChunk {
  answerId: string
  textChunk: string
  citations: Array<{
    citationId: string
    type: 'audio' | 'slide' | 'board' | 'ocr'
    label: string
    tsStartMs?: number
    tsEndMs?: number
    sourceFrameId?: string
  }>
}

export interface QaAnswerDone {
  answerId: string
  followups: string[]
}

export type WsEvent =
  | { type: 'session.status'; payload: { connection: ConnectionState } }
  | { type: 'transcript.partial'; payload: TranscriptLine }
  | { type: 'transcript.final'; payload: TranscriptLine }
  | { type: 'translation.final'; payload: { lineId: string; translatedText: string } }
  | { type: 'source.frame'; payload: SourceFrame }
  | { type: 'source.ocr'; payload: SourceOcrChunk }
  | { type: 'assist.summary'; payload: AssistSummaryPayload }
  | { type: 'assist.term'; payload: AssistTermPayload[] }
  | { type: 'qa.answer.chunk'; payload: QaAnswerChunk }
  | { type: 'qa.answer.done'; payload: QaAnswerDone }
  | { type: 'error'; payload: { message: string; recoverable: boolean } }

export interface StreamTransport {
  connect(sessionId: string): Promise<void>
  disconnect(): void
  send(event: WsEvent): void
  onEvent(handler: (event: WsEvent) => void): () => void
}

export interface LiveUiState {
  connection: ConnectionState
  transcriptLagMs: number
  translationLagMs: number
  sourceLagMs: number
  autoScroll: boolean
  selectedLanguage: 'ja' | 'easy-ja' | 'en'
  transcriptDensity: TranscriptDensity
  leftPanelMode: LeftPanelMode
}
