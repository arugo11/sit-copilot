/**
 * Lectures List Page
 * Session-driven lecture list backed by real APIs
 */

import { Link } from 'react-router-dom'
import { useCallback, useMemo, useState } from 'react'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'
import { demoApi, getApiErrorMessage } from '@/lib/api/client'

const DEMO_SESSIONS_STORAGE_KEY = 'sit_copilot_demo_sessions_v1'
const DEFAULT_SESSION_TITLE_PREFIX = '講義セッション '
const MAX_AUTO_SESSION_TITLE_LENGTH = 28

type SessionStatus = 'live' | 'ended'
type FilterType = 'all' | SessionStatus
type PersistedSessionStatus = SessionStatus | 'active' | 'finalized'

interface DemoLectureSession {
  session_id: string
  course_name: string
  started_at: string
  status: SessionStatus
}

function normalizeSessionStatus(value: unknown): SessionStatus | null {
  if (value === 'live' || value === 'active') {
    return 'live'
  }
  if (value === 'ended' || value === 'finalized') {
    return 'ended'
  }
  return null
}

function isPlaceholderSessionTitle(title: string): boolean {
  return title.startsWith(DEFAULT_SESSION_TITLE_PREFIX)
}

function normalizeTitleText(text: string): string {
  return text
    .replace(/\s+/gu, ' ')
    .replace(/[「」『』【】]/gu, '')
    .trim()
}

function truncateTitle(title: string): string {
  if (title.length <= MAX_AUTO_SESSION_TITLE_LENGTH) {
    return title
  }
  return `${title.slice(0, MAX_AUTO_SESSION_TITLE_LENGTH)}…`
}

function buildAutoSessionTitle(summary: string, firstKeyTerm?: string): string | null {
  const firstSentence = normalizeTitleText(summary.split(/[。.!?！？]/u)[0] ?? '')
  const normalizedKeyTerm = normalizeTitleText(firstKeyTerm ?? '')
  const merged = normalizedKeyTerm
    ? `${normalizedKeyTerm} / ${firstSentence || normalizedKeyTerm}`
    : firstSentence
  if (!merged) {
    return null
  }
  return truncateTitle(merged)
}

function isDemoLectureSession(value: unknown): value is DemoLectureSession {
  if (!value || typeof value !== 'object') {
    return false
  }
  const candidate = value as Record<string, unknown>
  const normalizedStatus = normalizeSessionStatus(candidate.status)
  return (
    typeof candidate.session_id === 'string' &&
    typeof candidate.course_name === 'string' &&
    typeof candidate.started_at === 'string' &&
    normalizedStatus !== null
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
    return parsed
      .filter(isDemoLectureSession)
      .map((session) => {
        const normalizedStatus = normalizeSessionStatus(
          (session as { status: PersistedSessionStatus }).status
        )
        return {
          ...session,
          status: normalizedStatus ?? 'live',
        }
      })
  } catch {
    return []
  }
}

function saveStoredSessions(sessions: DemoLectureSession[]): void {
  try {
    localStorage.setItem(DEMO_SESSIONS_STORAGE_KEY, JSON.stringify(sessions))
  } catch {
    // Ignore storage persistence failures in session mode
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
  isDeleting: boolean
  onFinalize: (sessionId: string) => Promise<void>
  onDelete: (session: DemoLectureSession) => Promise<void>
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

function SessionCard({
  session,
  isFinalizing,
  isDeleting,
  onFinalize,
  onDelete,
}: SessionCardProps) {
  const isBusy = isFinalizing || isDeleting

  return (
    <div className="card p-6 space-y-4 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-semibold text-fg-primary line-clamp-2">
            {session.course_name}
          </h3>
          <div className="flex items-center gap-2">
            {getStatusBadge(session.status)}
            <button
              type="button"
              className="btn btn-ghost min-h-8 min-w-8 p-1.5 text-fg-secondary hover:text-danger"
              aria-label={`${session.course_name} を削除`}
              title="セッションを削除"
              onClick={() => onDelete(session)}
              disabled={isBusy}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3m-7 0h8" />
              </svg>
            </button>
          </div>
        </div>
        <CopyButton value={session.session_id} label={`セッション ID ${session.session_id} をコピー`} />
      </div>

      {/* Details */}
      <div className="space-y-1 text-sm text-fg-secondary">
        <p>
          <span role="img" aria-label="開始時刻">🕐</span>{' '}
          {formatDateTime(session.started_at)}
        </p>
      </div>

      {/* Actions */}
      <div className="space-y-2">
        {session.status === 'live' ? (
          <Link
            to={`/lectures/${session.session_id}/live`}
            className="btn btn-primary w-full text-center"
          >
            講義に入る
          </Link>
        ) : (
          <span className="btn btn-primary w-full text-center pointer-events-none opacity-60">
            終了済み（遷移なし）
          </span>
        )}
        {session.status === 'live' ? (
          <button
            type="button"
            className="btn btn-secondary w-full"
            disabled={isBusy}
            onClick={() => onFinalize(session.session_id)}
            aria-label={`${session.course_name} のセッションを終了`}
          >
            {isFinalizing ? '終了中...' : isDeleting ? '削除中...' : 'セッション終了'}
          </button>
        ) : (
          <span className="btn btn-ghost w-full text-center pointer-events-none text-fg-secondary">
            {isDeleting ? '削除中...' : '終了済み'}
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
  const [deletingSessionIds, setDeletingSessionIds] = useState<Set<string>>(
    () => new Set()
  )
  const [startErrorMessage, setStartErrorMessage] = useState<string | null>(null)

  const filteredSessions = useMemo(() => {
    if (filter === 'all') {
      return sessions
    }
    return sessions.filter((session) => session.status === filter)
  }, [filter, sessions])

  const removeSessionLocally = useCallback((sessionId: string): void => {
    setSessions((prev) => {
      const nextSessions = prev.filter((item) => item.session_id !== sessionId)
      saveStoredSessions(nextSessions)
      return nextSessions
    })
  }, [])

  const renameSessionLocally = useCallback((sessionId: string, courseName: string): void => {
    setSessions((prev) => {
      const nextSessions = prev.map((session) =>
        session.session_id === sessionId
          ? { ...session, course_name: courseName }
          : session
      )
      saveStoredSessions(nextSessions)
      return nextSessions
    })
  }, [])

  const updateSessionTitleFromContent = useCallback(
    async (sessionId: string): Promise<void> => {
      try {
        const latestSummary = await demoApi.getLatestSummary(sessionId)
        if (latestSummary.status !== 'ok') {
          return
        }

        const firstKeyTerm = latestSummary.key_terms.find(
          (term) => typeof term.term === 'string' && term.term.trim().length > 0
        )?.term
        const autoTitle = buildAutoSessionTitle(latestSummary.summary, firstKeyTerm)
        if (!autoTitle) {
          return
        }

        renameSessionLocally(sessionId, autoTitle)
        showToast({
          variant: 'info',
          title: 'タイトルを自動更新しました',
          message: autoTitle,
        })
      } catch {
        // Ignore auto-title failures and keep placeholder title.
      }
    },
    [renameSessionLocally, showToast]
  )

  const handleStartSession = async (): Promise<void> => {
    setIsStarting(true)
    setStartErrorMessage(null)

    const startedAt = new Date()
    const courseName = `講義セッション ${new Intl.DateTimeFormat('ja-JP', {
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

      const newSession: DemoLectureSession = {
        session_id: startResponse.session_id,
        course_name: courseName,
        started_at: startedAt.toISOString(),
        status: 'live',
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
        title: 'セッションを開始しました',
        message: `Session ID: ${startResponse.session_id}`,
      })
    } catch (error) {
      const message = getApiErrorMessage(error, 'セッション開始に失敗しました。')
      setStartErrorMessage(message)
      showToast({
        variant: 'danger',
        title: 'セッション開始に失敗しました',
        message,
      })
    } finally {
      setIsStarting(false)
    }
  }

  const handleFinalizeSession = async (sessionId: string): Promise<void> => {
    // Guard: ignore re-click while this session is already being finalized
    if (finalizingSessionIds.has(sessionId) || deletingSessionIds.has(sessionId)) return
    const shouldAutoTitle = sessions.some(
      (session) =>
        session.session_id === sessionId &&
        isPlaceholderSessionTitle(session.course_name)
    )

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
      if (shouldAutoTitle) {
        void updateSessionTitleFromContent(sessionId)
      }
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
        if (shouldAutoTitle) {
          void updateSessionTitleFromContent(sessionId)
        }
      } else if (apiErr?.status === 404) {
        removeSessionLocally(sessionId)
        showToast({
          variant: 'warning',
          title: 'セッションが見つかりません',
          message: 'サーバー上に存在しないため一覧から削除しました。',
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

  const handleDeleteSession = async (session: DemoLectureSession): Promise<void> => {
    const sessionId = session.session_id
    if (deletingSessionIds.has(sessionId) || finalizingSessionIds.has(sessionId)) return

    const confirmed = window.confirm(
      `「${session.course_name}」を削除します。\nライブ中の場合は自動で終了してから削除されます。\nこの操作は取り消せません。`
    )
    if (!confirmed) {
      return
    }

    setDeletingSessionIds((prev) => new Set(prev).add(sessionId))
    try {
      const result = await demoApi.deleteDemoSession(sessionId)
      removeSessionLocally(sessionId)
      showToast({
        variant: 'success',
        title: 'セッションを削除しました',
        message: result.auto_finalized
          ? 'ライブ中セッションを自動終了して削除しました。'
          : undefined,
      })
    } catch (error) {
      const apiErr = error as { status?: number }
      if (apiErr?.status === 404) {
        removeSessionLocally(sessionId)
        showToast({
          variant: 'warning',
          title: 'セッションは既に削除済みです',
        })
      } else if (apiErr?.status === 409) {
        try {
          await demoApi.finalizeDemoSession(sessionId)
          const retryResult = await demoApi.deleteDemoSession(sessionId)
          removeSessionLocally(sessionId)
          showToast({
            variant: 'success',
            title: 'セッションを削除しました',
            message: retryResult.auto_finalized
              ? 'ライブ中セッションを自動終了して削除しました。'
              : '状態を同期後に削除しました。',
          })
        } catch (retryError) {
          const retryApiErr = retryError as { status?: number }
          if (retryApiErr?.status === 404) {
            removeSessionLocally(sessionId)
            showToast({
              variant: 'warning',
              title: 'セッションは既に削除済みです',
            })
          } else {
            showToast({
              variant: 'danger',
              title: 'セッション削除に失敗しました',
              message: getApiErrorMessage(
                retryError,
                'セッション状態の同期後も削除できませんでした。'
              ),
            })
          }
        }
      } else {
        showToast({
          variant: 'danger',
          title: 'セッション削除に失敗しました',
          message: getApiErrorMessage(error, 'セッション削除APIに失敗しました。'),
        })
      }
    } finally {
      setDeletingSessionIds((prev) => {
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
          {hasSessions ? '実APIで開始したセッションを一覧表示します' : 'ログイン不要でセッションを開始し、講義画面へ遷移できます'}
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-3 items-center">
        <button
          type="button"
          onClick={handleStartSession}
          disabled={isStarting}
          className="btn btn-primary"
        >
          {isStarting ? '開始中...' : 'セッション開始'}
        </button>
        {startErrorMessage && (
          <span className="text-sm text-danger">{startErrorMessage}</span>
        )}
      </div>

      {/* No data / error state */}
      {!hasSessions && (
        <EmptyState
          variant={startErrorMessage ? 'error' : 'no-data'}
          title={startErrorMessage ? '講義データの取得に失敗しました' : 'セッションがありません'}
          description={startErrorMessage ?? '「セッション開始」を押すと実APIでセッションを作成します。'}
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
                isDeleting={deletingSessionIds.has(session.session_id)}
                onFinalize={handleFinalizeSession}
                onDelete={handleDeleteSession}
              />
            ))}
          </div>
        )}
        </>
      )}
    </div>
  )
}
