import { create } from 'zustand'
import type { QaAnswerChunk, QaAnswerDone } from '@/lib/stream/types'

type QaStatus = 'idle' | 'streaming' | 'done' | 'error'

interface QaTurn {
  answerId: string
  question: string
  markdown: string
  status: QaStatus
  citations: QaAnswerChunk['citations']
  followups: string[]
}

interface ReviewQaStore {
  qaTurns: QaTurn[]
  currentStreamingAnswer: string | null
  status: QaStatus
  selectedCitation: string | null
  submitQuestion: (question: string, answerId: string) => void
  applyChunk: (chunk: QaAnswerChunk) => void
  applyDone: (done: QaAnswerDone) => void
  failAnswer: (answerId: string) => void
  retryAnswer: (answerId: string) => void
  selectCitation: (citationId: string | null) => void
  reset: () => void
}

export const useReviewQaStore = create<ReviewQaStore>((set) => ({
  qaTurns: [],
  currentStreamingAnswer: null,
  status: 'idle',
  selectedCitation: null,

  submitQuestion: (question, answerId) =>
    set((state) => ({
      qaTurns: [
        ...state.qaTurns,
        {
          answerId,
          question,
          markdown: '',
          status: 'streaming',
          citations: [],
          followups: [],
        },
      ],
      currentStreamingAnswer: answerId,
      status: 'streaming',
    })),

  applyChunk: (chunk) =>
    set((state) => ({
      qaTurns: state.qaTurns.map((turn) =>
        turn.answerId === chunk.answerId
          ? {
              ...turn,
              markdown: turn.markdown + chunk.textChunk,
              status: 'streaming',
              citations: [...turn.citations, ...chunk.citations],
            }
          : turn
      ),
      currentStreamingAnswer: chunk.answerId,
      status: 'streaming',
    })),

  applyDone: (done) =>
    set((state) => ({
      qaTurns: state.qaTurns.map((turn) =>
        turn.answerId === done.answerId
          ? {
              ...turn,
              status: 'done',
              followups: done.followups,
            }
          : turn
      ),
      currentStreamingAnswer: null,
      status: 'done',
    })),

  failAnswer: (answerId) =>
    set((state) => ({
      qaTurns: state.qaTurns.map((turn) =>
        turn.answerId === answerId
          ? { ...turn, status: 'error' }
          : turn
      ),
      currentStreamingAnswer:
        state.currentStreamingAnswer === answerId
          ? null
          : state.currentStreamingAnswer,
      status: 'error',
    })),

  retryAnswer: (answerId) =>
    set((state) => ({
      qaTurns: state.qaTurns.map((turn) =>
        turn.answerId === answerId
          ? {
              ...turn,
              markdown: '',
              status: 'streaming',
              citations: [],
              followups: [],
            }
          : turn
      ),
      currentStreamingAnswer: answerId,
      status: 'streaming',
    })),

  selectCitation: (selectedCitation) => set({ selectedCitation }),

  reset: () => set({ qaTurns: [], currentStreamingAnswer: null, status: 'idle', selectedCitation: null }),
}))
