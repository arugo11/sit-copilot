import type { ReactNode } from 'react'

interface Citation {
  citationId: string
  type: 'audio' | 'slide' | 'board' | 'ocr'
  label: string
  tsStartMs?: number
  tsEndMs?: number
  sourceFrameId?: string
}

interface QaTurn {
  answerId: string
  question: string
  markdown: string
  status: 'idle' | 'streaming' | 'done' | 'error'
  citations: Citation[]
  followups: string[]
}

export function QAStreamBlocks({
  turns,
  onCitationSelect,
  onRetry,
  onRegenerate,
  isBusy,
  labels,
}: {
  turns: QaTurn[]
  onCitationSelect: (citationId: string) => void
  onRetry: (answerId: string) => void
  onRegenerate: (question: string) => void
  isBusy: boolean
  labels: {
    resume: string
    regenerate: string
  }
}) {
  if (turns.length === 0) {
    return <div className="card p-4 text-sm text-fg-secondary">質問を入力すると回答ブロックがここに追加されます。</div>
  }

  return (
    <div className="space-y-4">
      {turns.map((turn) => (
        <article key={turn.answerId} className="card p-4 space-y-3">
          <header className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-fg-primary">Q. {turn.question}</h3>
            <StatusBadge status={turn.status} />
          </header>

          <div className="text-sm whitespace-pre-wrap leading-relaxed">
            {turn.markdown || '生成開始待ち...'}
          </div>

          <div className="flex flex-wrap gap-2" role="group" aria-label="引用元">
            {turn.citations.map((citation) => (
              <button
                key={citation.citationId}
                type="button"
                className="badge badge-default cursor-pointer"
                onClick={() => onCitationSelect(citation.citationId)}
              >
                {citation.label}
              </button>
            ))}
          </div>

          <Footer
            turn={turn}
            onRetry={onRetry}
            onRegenerate={onRegenerate}
            isBusy={isBusy}
            labels={labels}
          />
        </article>
      ))}
    </div>
  )
}

function StatusBadge({ status }: { status: QaTurn['status'] }): ReactNode {
  if (status === 'streaming') {
    return <span className="badge badge-warning">streaming</span>
  }
  if (status === 'done') {
    return <span className="badge badge-success">done</span>
  }
  if (status === 'error') {
    return <span className="badge badge-danger">error</span>
  }
  return <span className="badge badge-default">idle</span>
}

function Footer({
  turn,
  onRetry,
  onRegenerate,
  isBusy,
  labels,
}: {
  turn: QaTurn
  onRetry: (answerId: string) => void
  onRegenerate: (question: string) => void
  isBusy: boolean
  labels: {
    resume: string
    regenerate: string
  }
}) {
  return (
    <div className="pt-2 border-t border-border flex flex-wrap gap-2 items-center justify-between">
      <div className="flex flex-wrap gap-2">
        {turn.followups.map((followup) => (
          <span key={followup} className="badge badge-default">{followup}</span>
        ))}
      </div>
      {turn.status === 'error' ? (
        <div className="flex gap-2">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={isBusy}
            onClick={() => onRetry(turn.answerId)}
          >
            {labels.resume}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={isBusy}
            onClick={() => onRegenerate(turn.question)}
          >
            {labels.regenerate}
          </button>
        </div>
      ) : null}
    </div>
  )
}
