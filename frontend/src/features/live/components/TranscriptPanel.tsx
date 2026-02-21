import { useEffect, useMemo, useRef } from 'react'
import { SegmentedControl } from '@/components/ui'
import { formatTime } from '@/lib/utils'
import { useLiveSessionStore } from '@/stores/liveSessionStore'

export function TranscriptPanel() {
  const panelRef = useRef<HTMLDivElement | null>(null)
  const transcriptLines = useLiveSessionStore((state) => state.transcriptLines)
  const autoScroll = useLiveSessionStore((state) => state.autoScroll)
  const selectedLanguage = useLiveSessionStore((state) => state.selectedLanguage)
  const density = useLiveSessionStore((state) => state.transcriptDensity)
  const setAutoScroll = useLiveSessionStore((state) => state.setAutoScroll)
  const setSelectedLanguage = useLiveSessionStore((state) => state.setSelectedLanguage)
  const setTranscriptDensity = useLiveSessionStore((state) => state.setTranscriptDensity)

  const sortedLines = useMemo(
    () => [...transcriptLines].sort((a, b) => a.tsStartMs - b.tsStartMs),
    [transcriptLines]
  )

  useEffect(() => {
    if (!autoScroll || !panelRef.current) {
      return
    }
    panelRef.current.scrollTop = panelRef.current.scrollHeight
  }, [autoScroll, sortedLines.length])

  const handleScroll = () => {
    const el = panelRef.current
    if (!el) return
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30
    if (!isNearBottom && autoScroll) {
      setAutoScroll(false)
    }
  }

  const backToCurrent = () => {
    const el = panelRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    setAutoScroll(true)
  }

  return (
    <div className="h-full flex flex-col relative">
      <div className="p-3 border-b border-border bg-bg-surface flex flex-wrap gap-3 items-center">
        <SegmentedControl
          ariaLabel="language"
          value={selectedLanguage}
          onChange={(value) => setSelectedLanguage(value as 'ja' | 'en')}
          options={[
            { value: 'ja', label: '日本語表示' },
            { value: 'en', label: 'English view' },
          ]}
        />
        <SegmentedControl
          ariaLabel="density"
          value={density}
          onChange={(value) => setTranscriptDensity(value as 'comfortable' | 'compact')}
          options={[
            { value: 'comfortable', label: '標準' },
            { value: 'compact', label: 'コンパクト' },
          ]}
        />
        <label className="text-sm text-fg-secondary inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          自動スクロール
        </label>
      </div>

      <div ref={panelRef} className="flex-1 overflow-y-auto p-4 space-y-3" onScroll={handleScroll}>
        {sortedLines.length === 0 ? (
          <div className="card p-4 text-sm text-fg-secondary">字幕待機中です</div>
        ) : (
          sortedLines.map((line) => (
            <article
              key={line.id}
              className={`card ${density === 'compact' ? 'p-3' : 'p-4'} ${line.isPartial ? 'opacity-60' : ''}`}
            >
              <div className="text-xs text-fg-secondary flex items-center gap-2 mb-1">
                <span>{formatTime(line.tsStartMs)}</span>
                {line.speakerLabel ? <span>• {line.speakerLabel}</span> : null}
                {line.isPartial ? <span className="badge badge-warning">partial</span> : <span className="badge badge-success">final</span>}
              </div>
              <p className="text-fg-primary leading-relaxed">{line.sourceLangText}</p>
              {line.translatedText && (
                <p className="text-fg-secondary mt-1 leading-relaxed">{line.translatedText}</p>
              )}
            </article>
          ))
        )}
      </div>

      {!autoScroll && (
        <div className="absolute bottom-4 right-4">
          <button type="button" className="btn btn-primary shadow-lg" onClick={backToCurrent}>
            現在位置に戻る
          </button>
        </div>
      )}
    </div>
  )
}
