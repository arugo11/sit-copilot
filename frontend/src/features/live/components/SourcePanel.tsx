import { useMemo } from 'react'
import { Tabs } from '@/components/ui'
import { formatTime } from '@/lib/utils'
import { useLiveSessionStore } from '@/stores/liveSessionStore'

export function SourcePanel() {
  const sourceFrames = useLiveSessionStore((state) => state.sourceFrames)
  const ocrChunks = useLiveSessionStore((state) => state.ocrChunks)

  const slideFrames = useMemo(
    () => sourceFrames.filter((frame) => frame.source === 'slide'),
    [sourceFrames]
  )
  const boardFrames = useMemo(
    () => sourceFrames.filter((frame) => frame.source === 'board'),
    [sourceFrames]
  )

  const slideTabContent = (
    <SourceFrameList
      title="投影資料"
      frames={slideFrames}
      ocrChunks={ocrChunks.filter((chunk) => chunk.source === 'slide')}
    />
  )

  const boardTabContent = (
    <SourceFrameList
      title="板書"
      frames={boardFrames}
      ocrChunks={ocrChunks.filter((chunk) => chunk.source === 'board')}
    />
  )

  return (
    <div className="space-y-3">
      <h2 className="text-base font-semibold text-fg-primary">資料</h2>
      <Tabs
        defaultTab="slide"
        tabs={[
          { value: 'slide', label: '投影資料', content: slideTabContent },
          { value: 'board', label: '板書', content: boardTabContent },
        ]}
      />
    </div>
  )
}

function SourceFrameList({
  title,
  frames,
  ocrChunks,
}: {
  title: string
  frames: Array<{ id: string; thumbnailUrl: string; ocrExcerpt: string; timestampMs: number }>
  ocrChunks: Array<{ frameId: string; timestampMs: number; text: string }>
}) {
  const latest = frames[0]

  return (
    <div className="space-y-3">
      {latest ? (
        <div className="card p-3 space-y-2">
          <div className="flex items-center justify-between text-xs text-fg-secondary">
            <span>{title} 最新</span>
            <span>{formatTime(latest.timestampMs)}</span>
          </div>
          <img
            src={latest.thumbnailUrl}
            alt={`${title} snapshot`}
            className="w-full rounded-md border border-border cursor-pointer"
            onClick={() => window.open(latest.thumbnailUrl, '_blank', 'noopener,noreferrer')}
          />
          <p className="text-sm text-fg-secondary">{latest.ocrExcerpt}</p>
        </div>
      ) : (
        <div className="card p-4 text-sm text-fg-secondary">{title}のフレーム待機中</div>
      )}

      <div className="card p-3 space-y-2">
        <h3 className="text-sm font-medium text-fg-primary">OCR 更新履歴</h3>
        {ocrChunks.length === 0 ? (
          <p className="text-sm text-fg-secondary">まだOCR更新はありません</p>
        ) : (
          <ul className="space-y-2">
            {ocrChunks.slice(0, 5).map((chunk) => (
              <li key={`${chunk.frameId}_${chunk.timestampMs}`} className="text-sm">
                <p className="text-fg-primary">{chunk.text}</p>
                <p className="text-xs text-fg-secondary">{formatTime(chunk.timestampMs)}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card p-3 space-y-2">
        <h3 className="text-sm font-medium text-fg-primary">直近履歴</h3>
        <div className="grid grid-cols-2 gap-2">
          {frames.slice(0, 10).map((frame) => (
            <button
              type="button"
              key={frame.id}
              className="rounded border border-border overflow-hidden text-left"
              onClick={() => window.open(frame.thumbnailUrl, '_blank', 'noopener,noreferrer')}
            >
              <img src={frame.thumbnailUrl} alt="history" className="w-full h-16 object-cover" />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
