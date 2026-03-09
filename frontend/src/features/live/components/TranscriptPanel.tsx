import { useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { SegmentedControl } from '@/components/ui'
import { formatTime } from '@/lib/utils'
import { useLiveSessionStore } from '@/stores/liveSessionStore'

function formatSubtitleId(serial: number): string {
  return `S-${String(serial).padStart(3, '0')}`
}

export function TranscriptPanel() {
  const { t } = useTranslation()
  const panelRef = useRef<HTMLDivElement | null>(null)
  const transcriptLines = useLiveSessionStore((state) => state.transcriptLines)
  const autoScroll = useLiveSessionStore((state) => state.autoScroll)
  const selectedLanguage = useLiveSessionStore((state) => state.selectedLanguage)
  const paidFeatureVisibility = useLiveSessionStore(
    (state) => state.paidFeatureVisibility
  )
  const density = useLiveSessionStore((state) => state.transcriptDensity)
  const translationFallbackActive = useLiveSessionStore(
    (state) => state.translationFallbackActive
  )
  const setAutoScroll = useLiveSessionStore((state) => state.setAutoScroll)
  const switchLanguage = useLiveSessionStore((state) => state.switchLanguage)
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

  const languageOptions = [
    { value: 'ja', label: t('transcriptPanel.language.ja') },
    { value: 'easy-ja', label: t('transcriptPanel.language.easyJa') },
    { value: 'en', label: t('transcriptPanel.language.en') },
  ].filter((option) => option.value === 'ja' || paidFeatureVisibility.translation)

  return (
    <div className="h-full flex flex-col relative">
      <div className="flex flex-wrap items-start gap-3 border-b border-border bg-bg-surface p-3">
        <SegmentedControl
          ariaLabel={t('transcriptPanel.languageAria')}
          value={selectedLanguage}
          onChange={(value) => {
            const mode = value as 'ja' | 'easy-ja' | 'en'
            void switchLanguage(mode)
          }}
          options={languageOptions}
          className="w-full sm:w-auto"
        />
        <SegmentedControl
          ariaLabel={t('transcriptPanel.densityAria')}
          value={density}
          onChange={(value) => setTranscriptDensity(value as 'comfortable' | 'compact')}
          options={[
            { value: 'comfortable', label: t('transcriptPanel.density.comfortable') },
            { value: 'compact', label: t('transcriptPanel.density.compact') },
          ]}
          className="w-full sm:w-auto"
        />
        <label className="inline-flex min-h-10 items-center gap-2 text-sm text-fg-secondary">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(event) => setAutoScroll(event.target.checked)}
          />
          {t('transcriptPanel.autoScroll')}
        </label>
        {selectedLanguage !== 'ja' && translationFallbackActive && (
          <span className="badge badge-warning">{t('transcriptPanel.translationFallbackActive')}</span>
        )}
      </div>

      <div ref={panelRef} className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3" onScroll={handleScroll}>
        {sortedLines.length === 0 ? (
          <div className="card p-4 text-sm text-fg-secondary">{t('transcriptPanel.waiting')}</div>
        ) : (
          sortedLines.map((line) => {
            const originalText = (line.originalLangText ?? '').trim()
            const currentText = (line.sourceLangText ?? '').trim()
            const hasCorrectionDiff =
              originalText.length > 0 && currentText.length > 0 && originalText !== currentText

            return (
              <article
                key={line.id}
                className={`card ${density === 'compact' ? 'p-3' : 'p-4'} ${line.isPartial ? 'opacity-60' : ''}`}
              >
                <div className="text-xs text-fg-secondary flex items-center gap-2 mb-1">
                  {typeof line.subtitleSerial === 'number' && (
                    <span className="badge badge-default">
                      {t('transcriptPanel.subtitleId', { id: formatSubtitleId(line.subtitleSerial) })}
                    </span>
                  )}
                  <span>{formatTime(line.tsStartMs)}</span>
                  {line.speakerLabel ? <span>• {line.speakerLabel}</span> : null}
                  {line.isPartial ? (
                    <span className="badge badge-warning">{t('transcriptPanel.partial')}</span>
                  ) : (
                    <span className="badge badge-success">{t('transcriptPanel.final')}</span>
                  )}
                </div>
                {selectedLanguage === 'ja' ? (
                  <>
                    <p className="text-fg-primary leading-relaxed">{line.sourceLangText}</p>
                    {hasCorrectionDiff && (
                      <p className="text-xs text-fg-secondary mt-2">
                        {t('transcriptPanel.beforeCorrection', { text: originalText })}
                      </p>
                    )}
                    {line.correctionStatus === 'pending' && (
                      <p className="text-xs text-fg-secondary mt-1">{t('transcriptPanel.correctionPending')}</p>
                    )}
                    {line.correctionStatus === 'review_failed' && (
                      <p className="text-xs text-warning mt-1">{t('transcriptPanel.correctionFailed')}</p>
                    )}
                  </>
                ) : (
                  <>
                    <p className="text-fg-primary leading-relaxed">
                      {line.translatedLangMode === selectedLanguage
                        ? line.translatedText
                        : line.sourceLangText}
                    </p>
                    {line.translatedLangMode === selectedLanguage &&
                      line.translationStatus === 'fallback' && (
                        <p className="text-xs text-warning mt-1">
                          {t('transcriptPanel.translationFallbackLine')}
                        </p>
                    )}
                    {line.translatedLangMode !== selectedLanguage && (
                      <p className="text-xs text-fg-secondary mt-1">{t('transcriptPanel.translationWaiting')}</p>
                    )}
                  </>
                )}
              </article>
            )
          })
        )}
      </div>

      {!autoScroll && (
        <div className="absolute bottom-3 right-3 sm:bottom-4 sm:right-4">
          <button type="button" className="btn btn-primary px-3 py-2 text-sm shadow-lg" onClick={backToCurrent}>
            {t('transcriptPanel.backToCurrent')}
          </button>
        </div>
      )}
    </div>
  )
}
