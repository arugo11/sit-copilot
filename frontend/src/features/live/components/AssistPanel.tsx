import { useState, useEffect, useCallback } from 'react'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useAudioInputStore } from '@/stores/audioInputStore'
import { demoApi } from '@/lib/api/client'
import { useToast } from '@/components/common/Toast'
import { ToggleSwitch } from '@/components/common/ToggleSwitch'

const LANG_MODE_OPTIONS = [
  { value: 'ja', label: '日本語' },
  { value: 'easy-ja', label: 'やさしい日本語' },
  { value: 'en', label: 'English' },
] as const

const SUMMARY_REFRESH_INTERVAL_MS = 30000 // 30 seconds

const QUICK_QUESTIONS = ['この式の意味', 'もう一度説明して', 'この単語を日本語で']

export function AssistPanel({ onAskMiniQuestion }: { onAskMiniQuestion: (q: string) => void }) {
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

  // Manual refresh function
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
          points: summary.summary.split('。').filter(Boolean).slice(0, 3)
        })
        setAssistTerms(summary.key_terms.map((term) => ({
          term: typeof term === 'string' ? term : term.term,
          explanation: typeof term === 'string' ? 'Generated from lecture summary evidence.' : (term.explanation || ''),
          translation: typeof term === 'string' ? term : (term.translation || term.term),
        })))
      }
    } catch (error) {
      console.warn('[summary] refresh failed:', error)
    } finally {
      setIsRefreshingSummary(false)
    }
  }, [sessionId, isRefreshingSummary, setAssistSummary, setAssistTerms])

  // Auto-refresh every 30 seconds (only when summary is enabled)
  // Also trigger an immediate fetch when summary is first enabled.
  useEffect(() => {
    if (!sessionId || !summaryEnabled) {
      return
    }
    // Immediate fetch on toggle-on so users don't wait 30 seconds
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
        title: '言語モードを切り替えました',
        message:
          value === 'ja'
            ? '日本語'
            : value === 'easy-ja'
              ? 'やさしい日本語'
              : 'English',
      })
    } catch {
      showToast({
        variant: 'danger',
        title: '言語モードの切り替えに失敗しました',
        message: '接続状態を確認して再試行してください。',
      })
    } finally {
      setIsUpdatingLangMode(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">言語モード</h2>
        <div className="flex flex-wrap gap-2" role="group" aria-label="言語モード選択">
          {LANG_MODE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`badge cursor-pointer ${
                langMode === option.value
                  ? 'badge-primary'
                  : 'badge-default'
              }`}
              onClick={() => handleLangModeChange(option.value)}
              disabled={isUpdatingLangMode}
              aria-pressed={langMode === option.value}
            >
              {isUpdatingLangMode && langMode === option.value ? '更新中...' : option.label}
            </button>
          ))}
        </div>
      </section>

      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">状態</h2>
        <StatusRow label="録音" value={isRecording ? 'ON' : 'OFF'} ok={isRecording} />
        <StatusRow label="文字起こし" value="稼働中" ok />
        <StatusRow label="翻訳" value="稼働中" ok />
        <StatusRow label="資料OCR" value="稼働中" ok />
        <StatusRow label="接続" value={connection} ok={connection === 'live'} />
        <div className="mt-2">
          <div className="text-xs text-fg-secondary mb-1">マイク入力レベル</div>
          <div className="h-2 rounded bg-bg-muted overflow-hidden">
            <div className="h-full bg-accent transition-all" style={{ width: `${Math.round(audioLevel * 100)}%` }} />
          </div>
        </div>
      </section>

      <section className="card p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">いまの要点</h2>
            <ToggleSwitch checked={summaryEnabled} onChange={toggleSummary} label="要約機能の切り替え" />
          </div>
          <button
            type="button"
            className="btn btn-xs btn-secondary"
            onClick={handleRefreshSummary}
            disabled={!summaryEnabled || isRefreshingSummary || !sessionId}
          >
            {isRefreshingSummary ? '更新中...' : '今すぐ更新'}
          </button>
        </div>
        {!summaryEnabled ? (
          <p className="text-sm text-fg-secondary">現在この機能はOFFになっています</p>
        ) : summaryPoints.length === 0 ? (
          <p className="text-sm text-fg-secondary">要点生成待機中</p>
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
          <h2 className="text-sm font-semibold">用語サポート</h2>
          <ToggleSwitch checked={keytermsEnabled} onChange={toggleKeyterms} label="用語抽出機能の切り替え" />
        </div>
        {!keytermsEnabled ? (
          <p className="text-sm text-fg-secondary">現在この機能はOFFになっています</p>
        ) : assistTerms.length === 0 ? (
          <p className="text-sm text-fg-secondary">用語抽出待機中</p>
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
        <h2 className="text-sm font-semibold">質問候補</h2>
        <div className="flex flex-wrap gap-2">
          {QUICK_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              className="badge badge-default cursor-pointer"
              onClick={() => onAskMiniQuestion(question)}
            >
              {question}
            </button>
          ))}
        </div>
        <div className="pt-2 border-t border-border">
          <label className="block text-xs text-fg-secondary mb-1" htmlFor="mini-qa-input">ミニ質問</label>
          <div className="flex gap-2">
            <input
              id="mini-qa-input"
              className="input"
              value={miniQuestion}
              onChange={(e) => setMiniQuestion(e.target.value)}
              placeholder="短い質問を入力"
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                const q = miniQuestion.trim()
                if (!q) return
                onAskMiniQuestion(q)
                setMiniQuestion('')
              }}
            >
              送信
            </button>
          </div>
        </div>
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
