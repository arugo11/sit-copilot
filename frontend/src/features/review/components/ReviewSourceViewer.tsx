import type { ReviewSourceViewItem } from '@/features/review/reviewSourceView'

interface ReviewSourceViewerProps {
  source: ReviewSourceViewItem
}

export function ReviewSourceViewer({ source }: ReviewSourceViewerProps) {
  return (
    <div className="space-y-3">
      <h2 className="font-semibold">ソースビューア</h2>
      <div className="card p-3 space-y-2">
        <p className="text-xs text-fg-secondary">選択中: {source.title}</p>
        <p className="text-sm text-fg-primary">{source.transcript}</p>
        <img
          src={source.snapshot}
          alt="source"
          className="w-full rounded border border-border"
        />
      </div>
    </div>
  )
}
