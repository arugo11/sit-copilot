import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useAudioInputStore } from '@/stores/audioInputStore'
import { demoApi } from '@/lib/api/client'
import { useToast } from '@/components/common/Toast'
import { ToggleSwitch } from '@/components/common/ToggleSwitch'
import {
  QAStreamBlocks,
  type QaStreamStatus,
  type QaStreamTurn,
} from '@/features/review/components/QAStreamBlocks'

const SUMMARY_REFRESH_INTERVAL_MS = 30000 // 30 seconds

interface AssistPanelProps {
  onAskMiniQuestion: (q: string) => void
  qaTurns: QaStreamTurn[]
  qaStatus: QaStreamStatus
  isQaSubmitting: boolean
  onQaCitationSelect: (citationId: string) => void
  onQaRetry: (answerId: string) => void
  onQaRegenerate: (question: string) => void
}

export function AssistPanel({
  onAskMiniQuestion,
  qaTurns,
  qaStatus,
  isQaSubmitting,
  onQaCitationSelect,
  onQaRetry,
  onQaRegenerate,
}: AssistPanelProps) {
  const { t } = useTranslation()
  const { showToast } = useToast()
  const connection = useLiveSessionStore((state) => state.connection)
  const summaryPoints = useLiveSessionStore((state) => state.summaryPoints)
  const assistTerms = useLiveSessionStore((state) => state.assistTerms)
  const langMode = useLiveSessionStore((state) => state.langMode)
  const switchLanguage = useLiveSessionStore((state) => state.switchLanguage)
  const sessionId = useLiveSessionStore((state) => state.sessionId)
  const setAssistSummary = useLiveSessionStore((state) => state.setAssistSummary)
  const setAssistTerms = useLiveSessionStore((state) => state.setAssistTerms)
  const summaryEnabled = useLiveSessionStore((state) => state.summaryEnabled)
  const keytermsEnabled = useLiveSessionStore((state) => state.keytermsEnabled)
  const toggleSummary = useLiveSessionStore((state) => state.toggleSummary)
  const toggleKeyterms = useLiveSessionStore((state) => state.toggleKeyterms)
  const [miniQuestion, setMiniQuestion] = useState('')
  const [isUpdatingLangMode, setIsUpdatingLangMode] = useState(false)
  const [isRefreshingSummary, setIsRefreshingSummary] = useState(false)

  const langModeOptions = [
    { value: 'ja', label: t('assistPanel.languageModes.ja') },
    { value: 'easy-ja', label: t('assistPanel.languageModes.easyJa') },
    { value: 'en', label: t('assistPanel.languageModes.en') },
  ] as const

  const qaStatusLabel = {
    idle: t('assistPanel.qaStatus.idle'),
    streaming: t('assistPanel.qaStatus.streaming'),
    done: t('assistPanel.qaStatus.done'),
    error: t('assistPanel.qaStatus.error'),
  } as const

  const handleRefreshSummary = useCallback(async () => {
    if (!sessionId || isRefreshingSummary) {
      return
    }
    setIsRefreshingSummary(true)
    try {
      const summary = await demoApi.getLatestSummary(sessionId)
      if (summary.status === 'ok') {
        setAssistSummary({
          timestampMs: Date.now(),
          points: summary.summary.split('。').filter(Boolean).slice(0, 3),
        })
        setAssistTerms(
          summary.key_terms.map((term) => ({
            term: typeof term === 'string' ? term : term.term,
            explanation:
              typeof term === 'string'
                ? 'Generated from lecture summary evidence.'
                : (term.explanation || ''),
            translation:
              typeof term === 'string' ? term : (term.translation || term.term),
          }))
        )
      }
    } catch (error) {
      console.warn('[summary] refresh failed:', error)
    } finally {
      setIsRefreshingSummary(false)
    }
  }, [sessionId, isRefreshingSummary, setAssistSummary, setAssistTerms])

  useEffect(() => {
    if (!sessionId || !summaryEnabled) {
      return
    }
    handleRefreshSummary()
    const interval = setInterval(() => {
      handleRefreshSummary()
    }, SUMMARY_REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [sessionId, summaryEnabled, handleRefreshSummary])

  const isRecording = useAudioInputStore((state) => state.isRecording)
  const audioLevel = useAudioInputStore((state) => state.audioLevel)

  const handleLangModeChange = async (value: 'ja' | 'easy-ja' | 'en') => {
    setIsUpdatingLangMode(true)
    try {
      await switchLanguage(value)
      await handleRefreshSummary()
      showToast({
        variant: 'success',
        title: t('assistPanel.messages.langModeChangedTitle'),
        message:
          value === 'ja'
            ? t('assistPanel.languageModes.ja')
            : value === 'easy-ja'
              ? t('assistPanel.languageModes.easyJa')
              : t('assistPanel.languageModes.en'),
      })
    } catch {
      showToast({
        variant: 'danger',
        title: t('assistPanel.messages.langModeChangeFailedTitle'),
        message: t('assistPanel.messages.langModeChangeFailedMessage'),
      })
    } finally {
      setIsUpdatingLangMode(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">{t('assistPanel.sections.languageMode')}</h2>
        <div className="flex flex-wrap gap-2" role="group" aria-label={t('assistPanel.languageModeAria')}>
          {langModeOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`badge cursor-pointer ${
                langMode === option.value
                  ? 'bg-accent text-fg-inverse'
                  : 'badge-default'
              }`}
              onClick={() => handleLangModeChange(option.value)}
              disabled={isUpdatingLangMode}
              aria-pressed={langMode === option.value}
            >
              {isUpdatingLangMode && langMode === option.value
                ? t('assistPanel.updating')
                : option.label}
            </button>
          ))}
        </div>
      </section>

      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">{t('assistPanel.sections.status')}</h2>
        <StatusRow label={t('assistPanel.status.recording')} value={isRecording ? 'ON' : 'OFF'} ok={isRecording} />
        <StatusRow label={t('assistPanel.status.transcription')} value={t('assistPanel.status.running')} ok />
        <StatusRow label={t('assistPanel.status.translation')} value={t('assistPanel.status.running')} ok />
        <StatusRow label={t('assistPanel.status.connection')} value={t(`live.connection.${connection}`)} ok={connection === 'live'} />
        <div className="mt-2">
          <div className="text-xs text-fg-secondary mb-1">{t('assistPanel.status.micLevel')}</div>
          <div className="h-2 rounded bg-bg-muted overflow-hidden">
            <div className="h-full bg-accent transition-all" style={{ width: `${Math.round(audioLevel * 100)}%` }} />
          </div>
        </div>
      </section>

      <section className="card p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">{t('assistPanel.sections.summary')}</h2>
            <ToggleSwitch checked={summaryEnabled} onChange={toggleSummary} label={t('assistPanel.summaryToggleAria')} />
          </div>
          <button
            type="button"
            className="btn btn-xs btn-secondary"
            onClick={handleRefreshSummary}
            disabled={!summaryEnabled || isRefreshingSummary || !sessionId}
          >
            {isRefreshingSummary ? t('assistPanel.updating') : t('assistPanel.refreshNow')}
          </button>
        </div>
        {!summaryEnabled ? (
          <p className="text-sm text-fg-secondary">{t('assistPanel.summary.off')}</p>
        ) : summaryPoints.length === 0 ? (
          <p className="text-sm text-fg-secondary">{t('assistPanel.summary.waiting')}</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {summaryPoints.map((point) => (
              <li key={point} className="bg-bg-muted rounded px-2 py-1">• {point}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="card p-3 space-y-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">{t('assistPanel.sections.keyterms')}</h2>
          <ToggleSwitch checked={keytermsEnabled} onChange={toggleKeyterms} label={t('assistPanel.keytermsToggleAria')} />
        </div>
        {!keytermsEnabled ? (
          <p className="text-sm text-fg-secondary">{t('assistPanel.keyterms.off')}</p>
        ) : assistTerms.length === 0 ? (
          <p className="text-sm text-fg-secondary">{t('assistPanel.keyterms.waiting')}</p>
        ) : (
          <ul className="space-y-2">
            {assistTerms.map((term) => (
              <li key={term.term} className="text-sm">
                <p className="font-medium text-fg-primary">{term.term} <span className="text-fg-secondary">({term.translation})</span></p>
                <p className="text-fg-secondary">{term.explanation}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card p-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">{t('assistPanel.sections.qa')}</h2>
          <span
            className={`badge ${
              qaStatus === 'streaming'
                ? 'badge-warning'
                : qaStatus === 'error'
                  ? 'badge-danger'
                  : 'badge-success'
            }`}
          >
            {qaStatusLabel[qaStatus]}
          </span>
        </div>
        <div className="pt-2 border-t border-border">
          <label className="block text-xs text-fg-secondary mb-1" htmlFor="mini-qa-input">{t('assistPanel.miniQuestionLabel')}</label>
          <div className="flex gap-2">
            <input
              id="mini-qa-input"
              className="input"
              value={miniQuestion}
              onChange={(event) => setMiniQuestion(event.target.value)}
              placeholder={t('assistPanel.miniQuestionPlaceholder')}
              disabled={isQaSubmitting}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={isQaSubmitting}
              onClick={() => {
                const q = miniQuestion.trim()
                if (!q) return
                onAskMiniQuestion(q)
                setMiniQuestion('')
              }}
            >
              {isQaSubmitting ? t('assistPanel.submitting') : t('assistPanel.submit')}
            </button>
          </div>
        </div>
        <QAStreamBlocks
          turns={qaTurns}
          isBusy={isQaSubmitting}
          labels={{ resume: t('assistPanel.retry'), regenerate: t('assistPanel.regenerate') }}
          onCitationSelect={onQaCitationSelect}
          onRetry={onQaRetry}
          onRegenerate={onQaRegenerate}
        />
      </section>
    </div>
  )
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-fg-secondary">{label}</span>
      <span className={`inline-flex items-center gap-1 ${ok ? 'text-success' : 'text-warning'}`}>
        <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-success' : 'bg-warning'}`} />
        {value}
      </span>
    </div>
  )
}
