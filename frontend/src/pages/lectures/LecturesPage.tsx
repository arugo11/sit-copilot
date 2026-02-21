/**
 * Lectures List Page
 * Session-driven demo list backed by real APIs
 */

import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'
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
    live: 'badge-danger',
    ended: 'badge-success',
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
        <p className="text-sm text-fg-secondary break-all">
          Session ID: {session.session_id}
        </p>
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
            Readiness Score: {session.readiness_score}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="grid grid-cols-2 gap-2">
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
          >
            {isFinalizing ? '終了中...' : 'セッション終了'}
          </button>
        ) : (
          <span className="btn btn-ghost w-full text-center pointer-events-none">
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
  const [finalizingSessionId, setFinalizingSessionId] = useState<string | null>(
    null
  )
  const [startErrorMessage, setStartErrorMessage] = useState<string | null>(null)

  const filteredSessions = useMemo(() => {
    if (filter === 'all') {
      return sessions
    }
    return sessions.filter((session) => session.status === filter)
  }, [filter, sessions])

  const persistSessions = (nextSessions: DemoLectureSession[]): void => {
    setSessions(nextSessions)
    saveStoredSessions(nextSessions)
  }

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
            'このデモ講義では機械学習の基礎を扱います。評価はレポートと発表です。',
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
      const nextSessions = [
        newSession,
        ...sessions.filter((session) => session.session_id !== newSession.session_id),
      ]
      persistSessions(nextSessions)
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
    setFinalizingSessionId(sessionId)
    try {
      await demoApi.finalizeDemoSession(sessionId)
      const nextSessions = sessions.map((session) =>
        session.session_id === sessionId
          ? { ...session, status: 'ended' as const }
          : session
      )
      persistSessions(nextSessions)
      showToast({
        variant: 'success',
        title: 'セッションを終了しました',
      })
    } catch (error) {
      showToast({
        variant: 'danger',
        title: 'セッション終了に失敗しました',
        message: getApiErrorMessage(error, 'セッション終了APIに失敗しました。'),
      })
    } finally {
      setFinalizingSessionId(null)
    }
  }

  const hasSessions = sessions.length > 0
  const isFilteredEmpty = hasSessions && filteredSessions.length === 0
  const showErrorEmptyState = !hasSessions && Boolean(startErrorMessage)
  const showNoDataEmptyState = !hasSessions && !startErrorMessage

  if (showErrorEmptyState) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
          <p className="text-fg-secondary">
            ログイン不要のデモセッションを開始して講義画面へ遷移できます
          </p>
        </div>
        <div className="mb-6">
          <button
            type="button"
            onClick={handleStartSession}
            disabled={isStarting}
            className="btn btn-primary"
          >
            {isStarting ? '開始中...' : 'デモセッション開始'}
          </button>
        </div>
        <EmptyState
          variant="error"
          title="講義データの取得に失敗しました"
          description={startErrorMessage ?? undefined}
          action={
            <button onClick={handleStartSession} className="btn btn-primary">
              再試行
            </button>
          }
        />
      </div>
    )
  }

  if (showNoDataEmptyState) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
          <p className="text-fg-secondary">
            ログイン不要のデモセッションを開始して講義画面へ遷移できます
          </p>
        </div>

        <div className="mb-6">
          <button
            type="button"
            onClick={handleStartSession}
            disabled={isStarting}
            className="btn btn-primary"
          >
            {isStarting ? '開始中...' : 'デモセッション開始'}
          </button>
        </div>
        <EmptyState
          variant="no-data"
          title="デモセッションがありません"
          description="「デモセッション開始」を押すと実APIでセッションを作成します。"
        />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
        <p className="text-fg-secondary">
          実APIで開始したデモセッションを一覧表示します
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleStartSession}
          disabled={isStarting}
          className="btn btn-primary"
        >
          {isStarting ? '開始中...' : 'デモセッション開始'}
        </button>
        <span className="text-sm text-fg-secondary self-center">
          このブラウザでは localStorage に履歴を保存します
        </span>
      </div>

      {/* Filters */}
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
              isFinalizing={finalizingSessionId === session.session_id}
              onFinalize={handleFinalizeSession}
            />
          ))}
        </div>
      )}
    </div>
  )
}
