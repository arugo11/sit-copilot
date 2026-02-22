import type { ProcedureAskResponse, ProcedureSource } from '@/lib/api/client'
import type { QaAnswerChunk, QaAnswerDone } from '@/lib/stream/types'

function toCitation(
  answerId: string,
  source: ProcedureSource,
  index: number
): QaAnswerChunk['citations'][number] {
  const normalizedTitle = source.title.trim()
  const normalizedSection = source.section.trim()
  const labelBase = normalizedTitle || normalizedSection || source.source_id
  const label = normalizedSection
    ? `${labelBase} / ${normalizedSection}`
    : labelBase

  return {
    citationId: `${answerId}::${source.source_id}::${index}`,
    type: 'ocr',
    label,
    sourceFrameId: source.source_id,
  }
}

export function mapProcedureQaResponseToChunk(
  answerId: string,
  response: ProcedureAskResponse
): QaAnswerChunk {
  return {
    answerId,
    textChunk: response.answer,
    citations: response.sources.map((source, index) =>
      toCitation(answerId, source, index)
    ),
  }
}

export function mapProcedureQaResponseToDone(
  answerId: string,
  response: ProcedureAskResponse
): QaAnswerDone {
  return {
    answerId,
    followups: response.action_next.trim() ? [response.action_next] : [],
  }
}
