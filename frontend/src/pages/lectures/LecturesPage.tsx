/**
 * Lectures List Page
 * Session-driven demo list backed by real APIs
 */

import { Link } from 'react-router-dom'
import { useCallback, useMemo, useState } from 'react'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'
import { demoApi, getApiErrorMessage } from '@/lib/api/client'

const DEMO_SESSIONS_STORAGE_KEY = 'sit_copilot_demo_sessions_v1'

type SessionStatus = 'live' | 'ended'
type FilterType = 'all' | SessionStatus

interface DemoLectureSession {
  session_id: string
  course_name: string
  started_at: string
  status: SessionStatus
  readiness_score?: number
}

function isSessionStatus(value: unknown): value is SessionStatus {
  return value === 'live' || value === 'ended'
}

function isDemoLectureSession(value: unknown): value is DemoLectureSession {
  if (!value || typeof value !== 'object') {
    return false
  }
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.session_id === 'string' &&
    typeof candidate.course_name === 'string' &&
    typeof candidate.started_at === 'string' &&
    isSessionStatus(candidate.status)
  )
}

function loadStoredSessions(): DemoLectureSession[] {
  try {
    const raw = localStorage.getItem(DEMO_SESSIONS_STORAGE_KEY)
    if (!raw) {
      return []
    }
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter(isDemoLectureSession)
  } catch {
    return []
  }
}

function saveStoredSessions(sessions: DemoLectureSession[]): void {
  try {
    localStorage.setItem(DEMO_SESSIONS_STORAGE_KEY, JSON.stringify(sessions))
  } catch {
    // Ignore storage persistence failures in demo mode
  }
}

function formatDateTime(isoDatetime: string): string {
  const date = new Date(isoDatetime)
  if (Number.isNaN(date.getTime())) {
    return isoDatetime
  }
  return new Intl.DateTimeFormat('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function getStatusBadge(status: SessionStatus) {
  const variants = {
    live: 'badge-live',
    ended: 'badge-muted',
  }
  const labels = {
    live: 'ライブ中',
    ended: '終了',
  }
  return (
    <span className={`badge ${variants[status]}`}>
      {labels[status]}
    </span>
  )
}

interface SessionCardProps {
  session: DemoLectureSession
  isFinalizing: boolean
  onFinalize: (sessionId: string) => Promise<void>
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [value])
  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-xs text-fg-secondary hover:text-fg-primary transition-colors"
      aria-label={label}
      title={value}
    >
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        {copied
          ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        }
      </svg>
      {copied ? 'コピー済み' : 'ID をコピー'}
    </button>
  )
}

function SessionCard({ session, isFinalizing, onFinalize }: SessionCardProps) {
  return (
    <div className="card p-6 space-y-4 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-semibold text-fg-primary line-clamp-2">
            {session.course_name}
          </h3>
          {getStatusBadge(session.status)}
        </div>
        <CopyButton value={session.session_id} label={`セッション ID ${session.session_id} をコピー`} />
      </div>

      {/* Details */}
      <div className="space-y-1 text-sm text-fg-secondary">
        <p>
          <span role="img" aria-label="開始時刻">🕐</span>{' '}
          {formatDateTime(session.started_at)}
        </p>
        {typeof session.readiness_score === 'number' && (
          <p>
            <span role="img" aria-label="準備スコア">📊</span>{' '}
            準備スコア: {session.readiness_score}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="space-y-2">
        <Link
          to={
            session.status === 'live'
              ? `/lectures/${session.session_id}/live`
              : `/lectures/${session.session_id}/review`
          }
          className="btn btn-primary w-full text-center"
        >
          {session.status === 'live' ? '講義に入る' : 'レビューを見る'}
        </Link>
        {session.status === 'live' ? (
          <button
            type="button"
            className="btn btn-secondary w-full"
            disabled={isFinalizing}
            onClick={() => onFinalize(session.session_id)}
            aria-label={`${session.course_name} のセッションを終了`}
          >
            {isFinalizing ? '終了中...' : 'セッション終了'}
          </button>
        ) : (
          <span className="btn btn-ghost w-full text-center pointer-events-none text-fg-secondary">
            終了済み
          </span>
        )}
      </div>
    </div>
  )
}

export function LecturesPage() {
  const { showToast } = useToast()
  const [filter, setFilter] = useState<FilterType>('all')
  const [sessions, setSessions] = useState<DemoLectureSession[]>(() =>
    loadStoredSessions()
  )
  const [isStarting, setIsStarting] = useState<boolean>(false)
  const [finalizingSessionIds, setFinalizingSessionIds] = useState<Set<string>>(
    () => new Set()
  )
  const [startErrorMessage, setStartErrorMessage] = useState<string | null>(null)

  const filteredSessions = useMemo(() => {
    if (filter === 'all') {
      return sessions
    }
    return sessions.filter((session) => session.status === filter)
  }, [filter, sessions])

  const handleStartSession = async (): Promise<void> => {
    setIsStarting(true)
    setStartErrorMessage(null)

    const startedAt = new Date()
    const courseName = `デモ講義 ${new Intl.DateTimeFormat('ja-JP', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(startedAt)}`

    try {
      const startResponse = await demoApi.startDemoSession({
        course_name: courseName,
        camera_enabled: false,
        consent_acknowledged: true,
        lang_mode: 'ja',
      })

      let readinessScore: number | undefined
      try {
        const readinessResponse = await demoApi.checkReadiness({
          course_name: courseName,
          syllabus_text:
            'これはデモ文です。これは実データではありません。',
          lang_mode: 'ja',
        })
        readinessScore = readinessResponse.readiness_score
      } catch (error) {
        showToast({
          variant: 'warning',
          title: 'Readiness取得に失敗しました',
          message: getApiErrorMessage(error, 'readiness API request failed.'),
        })
      }

      const newSession: DemoLectureSession = {
        session_id: startResponse.session_id,
        course_name: courseName,
        started_at: startedAt.toISOString(),
        status: 'live',
        readiness_score: readinessScore,
      }
      // Use functional updater to avoid stale closure over sessions
      setSessions((prev) => {
        const nextSessions = [
          newSession,
          ...prev.filter((s) => s.session_id !== newSession.session_id),
        ]
        saveStoredSessions(nextSessions)
        return nextSessions
      })
      showToast({
        variant: 'success',
        title: 'デモセッションを開始しました',
        message: `Session ID: ${startResponse.session_id}`,
      })
    } catch (error) {
      const message = getApiErrorMessage(error, 'デモセッション開始に失敗しました。')
      setStartErrorMessage(message)
      showToast({
        variant: 'danger',
        title: 'デモセッション開始に失敗しました',
        message,
      })
    } finally {
      setIsStarting(false)
    }
  }

  const handleFinalizeSession = async (sessionId: string): Promise<void> => {
    // Guard: ignore re-click while this session is already being finalized
    if (finalizingSessionIds.has(sessionId)) return

    // Add to the set of in-progress finalizations (supports multiple concurrent)
    setFinalizingSessionIds((prev) => new Set(prev).add(sessionId))
    try {
      await demoApi.finalizeDemoSession(sessionId)
      // Use functional updater to avoid stale closure over sessions
      setSessions((prev) => {
        const nextSessions = prev.map((session) =>
          session.session_id === sessionId
            ? { ...session, status: 'ended' as const }
            : session
        )
        saveStoredSessions(nextSessions)
        return nextSessions
      })
      showToast({
        variant: 'success',
        title: 'セッションを終了しました',
      })
    } catch (error) {
      const apiErr = error as { status?: number }
      // 409 means session was already finalized on the server — update local state
      if (apiErr?.status === 409) {
        setSessions((prev) => {
          const nextSessions = prev.map((session) =>
            session.session_id === sessionId
              ? { ...session, status: 'ended' as const }
              : session
          )
          saveStoredSessions(nextSessions)
          return nextSessions
        })
        showToast({
          variant: 'success',
          title: 'セッションは既に終了済みです',
        })
      } else {
        showToast({
          variant: 'danger',
          title: 'セッション終了に失敗しました',
          message: getApiErrorMessage(error, 'セッション終了APIに失敗しました。'),
        })
      }
    } finally {
      // Remove from the set of in-progress finalizations
      setFinalizingSessionIds((prev) => {
        const next = new Set(prev)
        next.delete(sessionId)
        return next
      })
    }
  }

  const hasSessions = sessions.length > 0
  const isFilteredEmpty = hasSessions && filteredSessions.length === 0

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
        <p className="text-fg-secondary">
          {hasSessions ? '実APIで開始したデモセッションを一覧表示します' : 'ログイン不要のデモセッションを開始して講義画面へ遷移できます'}
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-3 items-center">
        <button
          type="button"
          onClick={handleStartSession}
          disabled={isStarting}
          className="btn btn-primary"
        >
          {isStarting ? '開始中...' : 'デモセッション開始'}
        </button>
        {startErrorMessage && (
          <span className="text-sm text-danger">{startErrorMessage}</span>
        )}
      </div>

      {/* No data / error state */}
      {!hasSessions && (
        <EmptyState
          variant={startErrorMessage ? 'error' : 'no-data'}
          title={startErrorMessage ? '講義データの取得に失敗しました' : 'デモセッションがありません'}
          description={startErrorMessage ?? '「デモセッション開始」を押すと実APIでセッションを作成します。'}
          action={
            startErrorMessage ? (
              <button onClick={handleStartSession} className="btn btn-primary">再試行</button>
            ) : undefined
          }
        />
      )}

      {/* Filters (only when sessions exist) */}
      {hasSessions && (
        <>
        <div className="flex flex-wrap gap-4 mb-6" role="group" aria-label="講義フィルター">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'all'}
          >
            すべて
          </button>
          <button
            type="button"
            onClick={() => setFilter('live')}
            className={`btn ${filter === 'live' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'live'}
          >
            ライブ中
          </button>
          <button
            type="button"
            onClick={() => setFilter('ended')}
            className={`btn ${filter === 'ended' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'ended'}
          >
            終了
          </button>
        </div>

        {/* Session Cards Grid */}
        {isFilteredEmpty ? (
          <EmptyState
            variant="no-results"
            title="該当するセッションがありません"
            description="フィルタ条件を変更するか、フィルタ解除を押してください。"
            action={
              <button type="button" className="btn btn-secondary" onClick={() => setFilter('all')}>
                フィルタ解除
              </button>
            }
          />
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredSessions.map((session) => (
              <SessionCard
                key={session.session_id}
                session={session}
                isFinalizing={finalizingSessionIds.has(session.session_id)}
                onFinalize={handleFinalizeSession}
              />
            ))}
          </div>
        )}
        </>
      )}
    </div>
  )
}
