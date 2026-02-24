/**
 * Lectures List Page
 * Session-driven lecture list backed by real APIs
 */

import { Link } from 'react-router-dom'
import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'
import {
  API_BASE_URL,
  DEMO_USER_ID,
  demoApi,
  getApiErrorMessage,
} from '@/lib/api/client'

const DEMO_SESSIONS_STORAGE_KEY_PREFIX = 'sit_copilot_demo_sessions_v2'
const DEFAULT_SESSION_TITLE_PREFIXES = ['講義セッション ', 'Lecture Session ']
const MAX_AUTO_SESSION_TITLE_LENGTH = 28

type SessionStatus = 'live' | 'ended'
type FilterType = 'all' | SessionStatus
type PersistedSessionStatus = SessionStatus | 'active' | 'finalized'

type UiLanguage = 'ja' | 'en'

interface DemoLectureSession {
  session_id: string
  course_name: string
  started_at: string
  status: SessionStatus
}

function buildDemoSessionsStorageKey(): string {
  const apiScope = API_BASE_URL || 'same-origin'
  return `${DEMO_SESSIONS_STORAGE_KEY_PREFIX}:${apiScope}:${DEMO_USER_ID}`
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
  return DEFAULT_SESSION_TITLE_PREFIXES.some((prefix) => title.startsWith(prefix))
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
  const storageKey = buildDemoSessionsStorageKey()
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) {
      return []
    }
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    const normalized = parsed
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
    const deduped: DemoLectureSession[] = []
    const seenSessionIds = new Set<string>()
    for (const session of normalized) {
      if (seenSessionIds.has(session.session_id)) {
        continue
      }
      seenSessionIds.add(session.session_id)
      deduped.push(session)
    }
    return deduped
  } catch {
    return []
  }
}

function saveStoredSessions(sessions: DemoLectureSession[]): void {
  const storageKey = buildDemoSessionsStorageKey()
  try {
    localStorage.setItem(storageKey, JSON.stringify(sessions))
  } catch {
    // Ignore storage persistence failures in session mode
  }
}

function formatDateTime(isoDatetime: string, language: UiLanguage): string {
  const date = new Date(isoDatetime)
  if (Number.isNaN(date.getTime())) {
    return isoDatetime
  }

  const locale = language === 'en' ? 'en-US' : 'ja-JP'
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function buildSessionStartTitle(startedAt: Date, language: UiLanguage): string {
  const locale = language === 'en' ? 'en-US' : 'ja-JP'
  const prefix = language === 'en' ? 'Lecture Session ' : '講義セッション '
  const formatted = new Intl.DateTimeFormat(locale, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(startedAt)
  return `${prefix}${formatted}`
}

interface SessionCardProps {
  session: DemoLectureSession
  locale: UiLanguage
  isFinalizing: boolean
  isDeleting: boolean
  onFinalize: (sessionId: string) => Promise<void>
  onDelete: (session: DemoLectureSession) => Promise<void>
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const { t } = useTranslation()
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
      {copied ? t('lectures.actions.copied') : t('lectures.actions.copyId')}
    </button>
  )
}

function SessionCard({
  session,
  locale,
  isFinalizing,
  isDeleting,
  onFinalize,
  onDelete,
}: SessionCardProps) {
  const { t } = useTranslation()
  const isBusy = isFinalizing || isDeleting

  const statusLabel =
    session.status === 'live'
      ? t('lectures.status.live')
      : t('lectures.status.ended')

  return (
    <div className="card p-6 space-y-4 hover:shadow-md transition-shadow">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-semibold text-fg-primary line-clamp-2">
            {session.course_name}
          </h3>
          <div className="flex items-center gap-2">
            <span className={`badge ${session.status === 'live' ? 'badge-live' : 'badge-muted'}`}>
              {statusLabel}
            </span>
            <button
              type="button"
              className="btn btn-ghost min-h-8 min-w-8 p-1.5 text-fg-secondary hover:text-danger"
              aria-label={t('lectures.actions.deleteSessionAria', { courseName: session.course_name })}
              title={t('lectures.actions.deleteSessionTitle')}
              onClick={() => onDelete(session)}
              disabled={isBusy}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3m-7 0h8" />
              </svg>
            </button>
          </div>
        </div>
        <CopyButton
          value={session.session_id}
          label={t('lectures.actions.copySessionIdAria', { sessionId: session.session_id })}
        />
      </div>

      <div className="space-y-1 text-sm text-fg-secondary">
        <p>
          <span role="img" aria-label={t('lectures.details.startedAt')}>🕐</span>{' '}
          {formatDateTime(session.started_at, locale)}
        </p>
      </div>

      <div className="space-y-2">
        {session.status === 'live' ? (
          <Link
            to={`/lectures/${session.session_id}/live`}
            className="btn btn-primary w-full text-center"
          >
            {t('lectures.actions.enter')}
          </Link>
        ) : (
          <span className="btn btn-primary w-full text-center pointer-events-none opacity-60">
            {t('lectures.actions.endedNoTransition')}
          </span>
        )}
        {session.status === 'live' ? (
          <button
            type="button"
            className="btn btn-secondary w-full"
            disabled={isBusy}
            onClick={() => onFinalize(session.session_id)}
            aria-label={t('lectures.actions.finalizeAria', { courseName: session.course_name })}
          >
            {isFinalizing
              ? t('lectures.actions.finalizing')
              : isDeleting
                ? t('lectures.actions.deleting')
                : t('lectures.actions.finalize')}
          </button>
        ) : (
          <span className="btn btn-ghost w-full text-center pointer-events-none text-fg-secondary">
            {isDeleting ? t('lectures.actions.deleting') : t('lectures.status.ended')}
          </span>
        )}
      </div>
    </div>
  )
}

export function LecturesPage() {
  const { t, i18n } = useTranslation()
  const { showToast } = useToast()
  const locale: UiLanguage =
    (i18n.resolvedLanguage ?? i18n.language).startsWith('en') ? 'en' : 'ja'

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
          title: t('lectures.messages.autoTitleUpdated'),
          message: autoTitle,
        })
      } catch {
        // Ignore auto-title failures and keep placeholder title.
      }
    },
    [renameSessionLocally, showToast, t]
  )

  const handleStartSession = async (): Promise<void> => {
    setIsStarting(true)
    setStartErrorMessage(null)

    const startedAt = new Date()
    const courseName = buildSessionStartTitle(startedAt, locale)

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
        title: t('lectures.messages.sessionStarted'),
        message: t('lectures.messages.sessionId', { sessionId: startResponse.session_id }),
      })
    } catch (error) {
      const message = getApiErrorMessage(error, t('lectures.messages.sessionStartFailed'))
      setStartErrorMessage(message)
      showToast({
        variant: 'danger',
        title: t('lectures.messages.sessionStartFailed'),
        message,
      })
    } finally {
      setIsStarting(false)
    }
  }

  const handleFinalizeSession = async (sessionId: string): Promise<void> => {
    if (finalizingSessionIds.has(sessionId) || deletingSessionIds.has(sessionId)) return

    const shouldAutoTitle = sessions.some(
      (session) =>
        session.session_id === sessionId &&
        isPlaceholderSessionTitle(session.course_name)
    )

    setFinalizingSessionIds((prev) => new Set(prev).add(sessionId))
    try {
      await demoApi.finalizeDemoSession(sessionId)
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
        title: t('lectures.messages.sessionFinalized'),
      })
      if (shouldAutoTitle) {
        void updateSessionTitleFromContent(sessionId)
      }
    } catch (error) {
      const apiErr = error as { status?: number }
      if (apiErr?.status === 409) {
        showToast({
          variant: 'warning',
          title: t('lectures.messages.sessionFinalizeFailed'),
          message: getApiErrorMessage(
            error,
            t('lectures.messages.sessionFinalizeApiFailed')
          ),
        })
      } else if (apiErr?.status === 404) {
        removeSessionLocally(sessionId)
        showToast({
          variant: 'warning',
          title: t('lectures.messages.sessionNotFound'),
          message: t('lectures.messages.sessionRemovedAfterNotFound'),
        })
      } else {
        showToast({
          variant: 'danger',
          title: t('lectures.messages.sessionFinalizeFailed'),
          message: getApiErrorMessage(error, t('lectures.messages.sessionFinalizeApiFailed')),
        })
      }
    } finally {
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
      t('lectures.messages.confirmDelete', { courseName: session.course_name })
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
        title: t('lectures.messages.sessionDeleted'),
        message: result.auto_finalized
          ? t('lectures.messages.sessionAutoFinalizedAndDeleted')
          : undefined,
      })
    } catch (error) {
      const apiErr = error as { status?: number }
      if (apiErr?.status === 404) {
        removeSessionLocally(sessionId)
        showToast({
          variant: 'warning',
          title: t('lectures.messages.sessionAlreadyDeleted'),
        })
      } else if (apiErr?.status === 409) {
        try {
          await demoApi.finalizeDemoSession(sessionId)
          const retryResult = await demoApi.deleteDemoSession(sessionId)
          removeSessionLocally(sessionId)
          showToast({
            variant: 'success',
            title: t('lectures.messages.sessionDeleted'),
            message: retryResult.auto_finalized
              ? t('lectures.messages.sessionAutoFinalizedAndDeleted')
              : t('lectures.messages.sessionDeletedAfterSync'),
          })
        } catch (retryError) {
          const retryApiErr = retryError as { status?: number }
          if (retryApiErr?.status === 404) {
            removeSessionLocally(sessionId)
            showToast({
              variant: 'warning',
              title: t('lectures.messages.sessionAlreadyDeleted'),
            })
          } else {
            showToast({
              variant: 'danger',
              title: t('lectures.messages.sessionDeleteFailed'),
              message: getApiErrorMessage(
                retryError,
                t('lectures.messages.sessionDeleteFailedAfterSync')
              ),
            })
          }
        }
      } else {
        showToast({
          variant: 'danger',
          title: t('lectures.messages.sessionDeleteFailed'),
          message: getApiErrorMessage(error, t('lectures.messages.sessionDeleteApiFailed')),
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
        <h1 className="text-3xl font-bold text-fg-primary mb-2">{t('lectures.title')}</h1>
        <p className="text-fg-secondary">
          {hasSessions
            ? t('lectures.pageDescription.withSessions')
            : t('lectures.pageDescription.withoutSessions')}
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-3 items-center">
        <button
          type="button"
          onClick={handleStartSession}
          disabled={isStarting}
          className="btn btn-primary"
        >
          {isStarting ? t('lectures.actions.starting') : t('lectures.actions.startSession')}
        </button>
        {startErrorMessage && (
          <span className="text-sm text-danger">{startErrorMessage}</span>
        )}
      </div>

      {!hasSessions && (
        <EmptyState
          variant={startErrorMessage ? 'error' : 'no-data'}
          title={
            startErrorMessage
              ? t('lectures.messages.fetchFailedTitle')
              : t('lectures.empty.title')
          }
          description={
            startErrorMessage
              ? startErrorMessage
              : t('lectures.empty.description')
          }
          action={
            startErrorMessage ? (
              <button onClick={handleStartSession} className="btn btn-primary">{t('common.retry')}</button>
            ) : undefined
          }
        />
      )}

      {hasSessions && (
        <>
          <div className="flex flex-wrap gap-4 mb-6" role="group" aria-label={t('lectures.filters.ariaLabel')}>
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}
              aria-pressed={filter === 'all'}
            >
              {t('lectures.filters.all')}
            </button>
            <button
              type="button"
              onClick={() => setFilter('live')}
              className={`btn ${filter === 'live' ? 'btn-primary' : 'btn-ghost'}`}
              aria-pressed={filter === 'live'}
            >
              {t('lectures.filters.live')}
            </button>
            <button
              type="button"
              onClick={() => setFilter('ended')}
              className={`btn ${filter === 'ended' ? 'btn-primary' : 'btn-ghost'}`}
              aria-pressed={filter === 'ended'}
            >
              {t('lectures.filters.ended')}
            </button>
          </div>

          {isFilteredEmpty ? (
            <EmptyState
              variant="no-results"
              title={t('lectures.empty.noResultsTitle')}
              description={t('lectures.empty.noResultsDescription')}
              action={
                <button type="button" className="btn btn-secondary" onClick={() => setFilter('all')}>
                  {t('lectures.empty.clearFilter')}
                </button>
              }
            />
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredSessions.map((session) => (
                <SessionCard
                  key={session.session_id}
                  session={session}
                  locale={locale}
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
