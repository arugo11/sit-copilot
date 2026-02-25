import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useAudioInputStore } from '@/stores/audioInputStore'
import { demoApi } from '@/lib/api/client'
import { useUserSettings, useUpdateSettings } from '@/lib/api/hooks'
import { useToast } from '@/components/common/Toast'
import { ToggleSwitch } from '@/components/common/ToggleSwitch'
import {
  mapSummaryKeyTermsToAssistTerms,
  mapSummaryResponseToAssist,
  mergeAssistSettingsForUpdate,
} from '@/features/live/utils/assistSupport'
import {
  QAStreamBlocks,
  type QaStreamStatus,
  type QaStreamTurn,
} from '@/features/review/components/QAStreamBlocks'

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
  const appendAssistTerms = useLiveSessionStore((state) => state.appendAssistTerms)
  const summaryEnabled = useLiveSessionStore((state) => state.summaryEnabled)
  const keytermsEnabled = useLiveSessionStore((state) => state.keytermsEnabled)
  const setSummaryEnabled = useLiveSessionStore((state) => state.setSummaryEnabled)
  const setKeytermsEnabled = useLiveSessionStore((state) => state.setKeytermsEnabled)
  const transcriptLines = useLiveSessionStore((state) => state.transcriptLines)
  const { data: userSettings } = useUserSettings()
  const updateSettingsMutation = useUpdateSettings()
  const [miniQuestion, setMiniQuestion] = useState('')
  const [isUpdatingLangMode, setIsUpdatingLangMode] = useState(false)
  const [isRefreshingSummary, setIsRefreshingSummary] = useState(false)
  const isRefreshingSummaryRef = useRef(false)
  const latestFinalSubtitleKey = useMemo(() => {
    const latestFinalLine = [...transcriptLines]
      .reverse()
      .find((line) => !line.isPartial && line.sourceLangText.trim().length > 0)

    if (!latestFinalLine) {
      return null
    }

    return `${latestFinalLine.id}:${latestFinalLine.sourceLangText.trim()}`
  }, [transcriptLines])

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
    if (!sessionId || isRefreshingSummaryRef.current) {
      return
    }
    isRefreshingSummaryRef.current = true
    setIsRefreshingSummary(true)
    try {
      const summary = await demoApi.getLatestSummary(sessionId)
      if (summary.status === 'ok') {
        const mapped = mapSummaryResponseToAssist(summary)
        setAssistSummary({
          timestampMs: Date.now(),
          points: mapped.points,
        })
      } else if (summary.status === 'off' || summary.status === 'no_data') {
        console.info('[summary] refresh non-ok status', {
          sessionId,
          status: summary.status,
          reason: summary.reason,
        })
        setAssistSummary({ timestampMs: Date.now(), points: [] })
      }
    } catch (error) {
      console.warn('[summary] refresh failed:', error)
    } finally {
      isRefreshingSummaryRef.current = false
      setIsRefreshingSummary(false)
    }
  }, [sessionId, setAssistSummary])

  useEffect(() => {
    if (!sessionId || !summaryEnabled || !latestFinalSubtitleKey) {
      return
    }
    void handleRefreshSummary()
  }, [sessionId, summaryEnabled, latestFinalSubtitleKey, handleRefreshSummary])

  const isRecording = useAudioInputStore((state) => state.isRecording)
  const audioLevel = useAudioInputStore((state) => state.audioLevel)

  const handleLangModeChange = async (value: 'ja' | 'easy-ja' | 'en') => {
    setIsUpdatingLangMode(true)
    try {
      await switchLanguage(value)
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

  const persistAssistToggle = useCallback(
    async (updates: { assistSummaryEnabled?: boolean; assistKeytermsEnabled?: boolean }) => {
      const nextSettings = mergeAssistSettingsForUpdate(userSettings, {
        assistSummaryEnabled:
          updates.assistSummaryEnabled ?? summaryEnabled,
        assistKeytermsEnabled:
          updates.assistKeytermsEnabled ?? keytermsEnabled,
      })
      await updateSettingsMutation.mutateAsync({ settings: nextSettings })
    },
    [keytermsEnabled, summaryEnabled, updateSettingsMutation, userSettings]
  )

  const handleSummaryToggleChange = useCallback(
    async (enabled: boolean) => {
      setSummaryEnabled(enabled)
      if (!enabled) {
        setAssistSummary({ timestampMs: Date.now(), points: [] })
      }

      try {
        await persistAssistToggle({ assistSummaryEnabled: enabled })
      } catch (error) {
        console.warn('[assist] failed to persist summary toggle', error)
      }

    },
    [persistAssistToggle, setAssistSummary, setSummaryEnabled]
  )

  const handleKeytermsToggleChange = useCallback(
    async (enabled: boolean) => {
      setKeytermsEnabled(enabled)
      if (!enabled) {
        setAssistTerms([])
      }

      try {
        await persistAssistToggle({ assistKeytermsEnabled: enabled })
      } catch (error) {
        console.warn('[assist] failed to persist keyterms toggle', error)
      }

      if (!enabled || !sessionId) {
        return
      }

      const latestFinalLine = [...transcriptLines]
        .reverse()
        .find((line) => !line.isPartial && line.sourceLangText.trim().length > 0)

      if (!latestFinalLine) {
        return
      }

      try {
        const keytermsResult = await demoApi.analyzeKeyterms({
          session_id: sessionId,
          transcript_text: latestFinalLine.sourceLangText.trim(),
          lang_mode: langMode,
        })
        if (keytermsResult.status === 'ok') {
          appendAssistTerms(mapSummaryKeyTermsToAssistTerms(keytermsResult.key_terms))
        } else {
          console.info('[assist] immediate keyterms non-ok status', {
            sessionId,
            status: keytermsResult.status,
            reason: keytermsResult.reason,
          })
        }
      } catch (error) {
        console.warn('[assist] immediate keyterms extraction failed', error)
      }
    },
    [
      langMode,
      persistAssistToggle,
      sessionId,
      appendAssistTerms,
      setAssistTerms,
      setKeytermsEnabled,
      transcriptLines,
    ]
  )

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
            <ToggleSwitch
              checked={summaryEnabled}
              onChange={() => {
                void handleSummaryToggleChange(!summaryEnabled)
              }}
              label={t('assistPanel.summaryToggleAria')}
            />
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
          <ToggleSwitch
            checked={keytermsEnabled}
            onChange={() => {
              void handleKeytermsToggleChange(!keytermsEnabled)
            }}
            label={t('assistPanel.keytermsToggleAria')}
          />
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
