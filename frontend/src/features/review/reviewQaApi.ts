import { lectureQaApi, type LectureQaLangMode } from '@/lib/api/client'

export const REVIEW_QA_TOP_K = 5
export const REVIEW_QA_CONTEXT_WINDOW = 1
export const REVIEW_QA_HISTORY_TURNS = 3

export function createReviewAnswerId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `qa_${crypto.randomUUID()}`
  }
  return `qa_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function resolveReviewQaLangMode(
  language: 'ja' | 'easy-ja' | 'en' | undefined
): LectureQaLangMode {
  if (language === 'en') {
    return 'en'
  }
  if (language === 'easy-ja') {
    return 'easy-ja'
  }
  return 'ja'
}

export async function warmupReviewQaIndex(sessionId: string): Promise<void> {
  await lectureQaApi.buildIndex({
    session_id: sessionId,
    rebuild: false,
  })
}

export async function requestReviewQaAnswer(params: {
  sessionId: string
  question: string
  language: 'ja' | 'easy-ja' | 'en' | undefined
  hasSuccessfulTurn: boolean
}) {
  const { sessionId, question, language, hasSuccessfulTurn } = params
  const basePayload = {
    session_id: sessionId,
    question,
    lang_mode: resolveReviewQaLangMode(language),
    retrieval_mode: 'source-only' as const,
    top_k: REVIEW_QA_TOP_K,
    context_window: REVIEW_QA_CONTEXT_WINDOW,
  }

  if (hasSuccessfulTurn) {
    return lectureQaApi.followup({
      ...basePayload,
      history_turns: REVIEW_QA_HISTORY_TURNS,
    })
  }
  return lectureQaApi.ask(basePayload)
}
