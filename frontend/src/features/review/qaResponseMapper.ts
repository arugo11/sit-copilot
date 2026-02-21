import type {
  LectureAskResponse,
  LectureFollowupResponse,
  LectureSource,
} from '@/lib/api/client'
import type { QaAnswerChunk, QaAnswerDone } from '@/lib/stream/types'

type LectureQaResponse = LectureAskResponse | LectureFollowupResponse

function mapSourceType(
  sourceType: LectureSource['type']
): QaAnswerChunk['citations'][number]['type'] {
  return sourceType === 'speech' ? 'audio' : 'ocr'
}

function toCitation(
  answerId: string,
  source: LectureSource,
  index: number
): QaAnswerChunk['citations'][number] {
  return {
    citationId: `${answerId}::${source.chunk_id}::${index}`,
    type: mapSourceType(source.type),
    label: source.timestamp && source.timestamp.trim() ? source.timestamp : source.chunk_id,
    tsStartMs: source.start_ms ?? undefined,
    tsEndMs: source.end_ms ?? undefined,
    sourceFrameId: source.type === 'visual' ? source.chunk_id : undefined,
  }
}

export function mapLectureQaResponseToChunk(
  answerId: string,
  response: LectureQaResponse
): QaAnswerChunk {
  return {
    answerId,
    textChunk: response.answer,
    citations: response.sources.map((source, index) =>
      toCitation(answerId, source, index)
    ),
  }
}

export function mapLectureQaResponseToDone(answerId: string): QaAnswerDone {
  return {
    answerId,
    followups: [],
  }
}
