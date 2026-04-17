/**
 * Lectures List Page
 * Session-driven lecture list backed by real APIs
 */

import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'
import {
  ApiError,
  API_BASE_URL,
  demoApi,
  getApiErrorMessage,
  lectureQaApi,
  type LectureQaLangMode,
} from '@/lib/api/client'

const DEMO_SESSIONS_STORAGE_KEY_PREFIX = 'sit_copilot_demo_sessions_v2'
const DEFAULT_SESSION_TITLE_PREFIXES = ['講義セッション ', 'Lecture Session ']
const MIN_AUTO_SESSION_TITLE_LENGTH = 2
const MAX_AUTO_SESSION_TITLE_LENGTH = 28
const MAX_AUTO_TITLE_CANDIDATES = 3
const MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS = 3
const AUTO_TITLE_RETRY_DELAY_MS = 1500
const AUTO_TITLE_QA_TOP_K = 5
const AUTO_TITLE_QA_CONTEXT_WINDOW = 1
const AUTO_TITLE_DEBUG_PREVIEW_LENGTH = 120
const MAX_MANUAL_SESSION_TITLE_LENGTH = 80
const AUTO_TITLE_SINGLE_WORD_PATTERN =
  /^[A-Za-z0-9\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}ー・-]+$/u
const AUTO_TITLE_PARTICLE_SUFFIXES = [
  'について',
  'において',
  'における',
  'による',
  'とは',
  'では',
  'での',
  'への',
  'から',
  'まで',
  'より',
  'など',
  'は',
  'が',
  'を',
  'に',
  'で',
  'と',
  'へ',
  'も',
  'や',
  'の',
] as const
const AUTO_TITLE_GENERATING_LABELS = {
  ja: 'タイトル作成中...',
  en: 'Generating title...',
} as const
const AUTO_TITLE_DEFAULT_LABELS = {
  ja: '講義セッション',
  en: 'Lecture Session',
} as const
const AUTO_TITLE_SINGLE_WORD_PROMPTS = {
  ja: [
    'このセッションのログだけを根拠に、最も重要な単語を1つだけ作成してください。',
    '出力条件: 1単語のみ、最大28文字、改行なし。',
    '出力形式は1行のみ: <word>...</word>',
    '説明文・前置き・ラベル（例: タイトル:）は絶対に出力しないでください。',
  ].join('\n'),
  en: [
    'Based only on this session log, generate exactly one most important word.',
    'Output constraints: one word only, max 28 characters, single line.',
    'Output format must be exactly one line: <word>...</word>',
    'Do not output any explanation, preface, or labels (e.g., "Title:").',
  ].join('\n'),
} as const
const AUTO_TITLE_SINGLE_WORD_JUDGE_PROMPTS = {
  ja: [
    '次の候補が「単語1つのみ」かを判定してください。',
    '判定条件: 空白なし、2〜28文字、説明文ではない。',
    '出力形式は1行のみ: <judge>OK</judge> または <judge>NG</judge>',
  ].join('\n'),
  en: [
    'Judge whether the following candidate is exactly one word.',
    'Criteria: no whitespace, 2-28 characters, not a sentence/explanation.',
    'Output format must be one line only: <judge>OK</judge> or <judge>NG</judge>',
  ].join('\n'),
} as const
const KNOWN_AUTO_TITLE_FALLBACK_MESSAGES = [
  '講義資料に該当する情報が見つかりませんでした。',
  '回答生成中にエラーが発生しました。講義資料を直接確認してください。',
  'No relevant information was found in the lecture materials.',
  'An error occurred while generating the answer. Please check the lecture materials directly.',
] as const
const AUTO_TITLE_EXACT_PLACEHOLDER_LABELS = [
  ...Object.values(AUTO_TITLE_DEFAULT_LABELS),
  ...Object.values(AUTO_TITLE_GENERATING_LABELS),
] as const

type SessionStatus = 'live' | 'ended'
type FilterType = 'all' | SessionStatus
type PersistedSessionStatus = SessionStatus | 'active' | 'finalized'
type AutoTitleDebugLogLevel = 'info' | 'warning' | 'error'
type AutoTitleJudgeVerdict = 'ok' | 'ng' | 'inconclusive'

type UiLanguage = 'ja' | 'en'

interface DemoLectureSession {
  session_id: string
  course_name: string
  started_at: string
  status: SessionStatus
}

function buildDemoSessionsStorageKey(): string {
  const apiScope = API_BASE_URL || 'same-origin'
  return `${DEMO_SESSIONS_STORAGE_KEY_PREFIX}:${apiScope}:public-demo`
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
  const normalized = normalizeGeneratedTitleCandidate(title)
  if (DEFAULT_SESSION_TITLE_PREFIXES.some((prefix) => normalized.startsWith(prefix))) {
    return true
  }
  return AUTO_TITLE_EXACT_PLACEHOLDER_LABELS.some(
    (label) => normalizeGeneratedTitleCandidate(label) === normalized
  )
}

function normalizeGeneratedTitleCandidate(text: string): string {
  const normalized = text
    .replace(/\r?\n|\r/gu, ' ')
    .replace(/\s+/gu, ' ')
    .trim()
  return normalized
    .replace(/^[「」『』"'()（）【】<>]+/gu, '')
    .replace(/[「」『』"'()（）【】<>]+$/gu, '')
    .trim()
}

function normalizeAutoTitleTagInput(text: string): string {
  return text
    .replace(/\r?\n|\r/gu, ' ')
    .replace(/\s+/gu, ' ')
    .trim()
}

function stripAutoTitleBoilerplatePrefix(text: string): string {
  return text
    .replace(/^講義資料(?:では|で|について|において)?/u, '')
    .replace(/^この(?:講義|セッション)(?:では|で|について|において)?/u, '')
    .replace(/^(?:講義|セッション)(?:では|で|について|において)?/u, '')
    .trim()
}

function trimAutoTitleParticleSuffix(token: string): string {
  let result = token
  for (const suffix of AUTO_TITLE_PARTICLE_SUFFIXES) {
    if (result.length <= suffix.length + 1) {
      continue
    }
    if (!result.endsWith(suffix)) {
      continue
    }
    result = result.slice(0, -suffix.length)
    break
  }
  return result
}

function trimAutoTitleParticleAlnumBoundary(token: string): string {
  const match = token.match(
    /^(.+?)(?:について|において|における|による|とは|では|での|への|から|まで|より|など|は|が|を|に|で|と|へ|も|や|の)(?=[0-9A-Za-z])/u
  )
  if (!match || !match[1]) {
    return token
  }
  return match[1]
}

function normalizeAutoTitleCandidate(text: string): string {
  const normalized = normalizeGeneratedTitleCandidate(text)
  if (!normalized) {
    return ''
  }

  const quotedMatch =
    normalized.match(/[「『"“](.+?)[」』"”]/u) ??
    normalized.match(/['](.+?)[']/u)
  const quotedCandidate = quotedMatch ? normalizeGeneratedTitleCandidate(quotedMatch[1]) : ''
  const source = quotedCandidate || normalized
  const withoutLabel = source
    .replace(/^[-*#>\s]+/gu, '')
    .replace(/^(?:候補|candidate|title|session title|keyword)\s*\d*\s*[:：-]\s*/iu, '')
    .replace(/[`*_]/gu, '')
    .trim()
  const withoutPrefix = stripAutoTitleBoilerplatePrefix(withoutLabel)
  const firstSegment = withoutPrefix.split(/[|｜]/u)[0] ?? withoutPrefix
  const firstWord = firstSegment.split(/\s+/u)[0] ?? firstSegment
  const punctuationTrimmed = (firstWord || firstSegment)
    .split(/[、,。.!?！？:：;；/／]/u)[0] ?? ''
  const normalizedCandidate = normalizeGeneratedTitleCandidate(punctuationTrimmed)
  const withoutBoundary = trimAutoTitleParticleAlnumBoundary(normalizedCandidate)
  const withoutParticle = trimAutoTitleParticleSuffix(withoutBoundary)
  return normalizeGeneratedTitleCandidate(withoutParticle)
}

function buildAutoTitleSingleWordPrompt(params: {
  locale: UiLanguage
  excludedCandidates: readonly string[]
}): string {
  const { locale, excludedCandidates } = params
  const basePrompt = AUTO_TITLE_SINGLE_WORD_PROMPTS[locale]
  if (excludedCandidates.length === 0) {
    return basePrompt
  }
  if (locale === 'en') {
    return [
      basePrompt,
      `Do not output these words: ${excludedCandidates.join(', ')}`,
    ].join('\n')
  }
  return [
    basePrompt,
    `次の単語は出力しないでください: ${excludedCandidates.join('、')}`,
  ].join('\n')
}

function buildAutoTitleJudgePrompt(params: {
  locale: UiLanguage
  candidate: string
}): string {
  const { locale, candidate } = params
  const basePrompt = AUTO_TITLE_SINGLE_WORD_JUDGE_PROMPTS[locale]
  if (locale === 'en') {
    return `${basePrompt}\nCandidate: ${candidate}`
  }
  return `${basePrompt}\n候補: ${candidate}`
}

function extractAutoTitleWordFromQaAnswer(text: string): string {
  const tagInput = normalizeAutoTitleTagInput(text)
  if (!tagInput) {
    return ''
  }

  const wordTaggedMatch = tagInput.match(/<word>\s*([^<]+?)\s*<\/word>/iu)
  if (wordTaggedMatch && wordTaggedMatch[1]) {
    return normalizeAutoTitleCandidate(wordTaggedMatch[1])
  }

  const titleTaggedMatch = tagInput.match(/<title>\s*([^<]+?)\s*<\/title>/iu)
  if (titleTaggedMatch && titleTaggedMatch[1]) {
    return normalizeAutoTitleCandidate(titleTaggedMatch[1])
  }

  const normalized = normalizeGeneratedTitleCandidate(tagInput)
  const firstLine = normalized.split(/\r?\n|\r/gu)[0] ?? normalized
  return normalizeAutoTitleCandidate(firstLine)
}

function parseAutoTitleJudgeVerdict(text: string): AutoTitleJudgeVerdict {
  const normalized = normalizeAutoTitleTagInput(text).toLowerCase()
  if (!normalized) {
    return 'inconclusive'
  }
  if (/<judge>\s*ok\s*<\/judge>/iu.test(normalized)) {
    return 'ok'
  }
  if (/^ok$/iu.test(normalized)) {
    return 'ok'
  }
  if (/<judge>\s*ng\s*<\/judge>/iu.test(normalized)) {
    return 'ng'
  }
  if (/^ng$/iu.test(normalized)) {
    return 'ng'
  }
  return 'inconclusive'
}

function isKnownAutoTitleFallback(title: string): boolean {
  return KNOWN_AUTO_TITLE_FALLBACK_MESSAGES.some(
    (fallback) => normalizeGeneratedTitleCandidate(fallback) === title
  )
}

function isKnownAutoTitleFallbackMessage(value: string | null | undefined): boolean {
  if (typeof value !== 'string') {
    return false
  }
  const normalized = normalizeGeneratedTitleCandidate(value)
  if (!normalized) {
    return false
  }
  return isKnownAutoTitleFallback(normalized)
}

async function waitForAutoTitleRetry(): Promise<void> {
  await new Promise((resolve) => {
    window.setTimeout(resolve, AUTO_TITLE_RETRY_DELAY_MS)
  })
}

function normalizeManualSessionTitle(text: string): string {
  return text
    .replace(/\r?\n|\r/gu, ' ')
    .replace(/\s+/gu, ' ')
    .trim()
}

function buildAutoTitleFromSummary(params: {
  summary: string
  keyTerms: readonly { term: string }[]
}): string[] {
  const { summary, keyTerms } = params
  const rawCandidates: string[] = []
  const normalizedSummary = normalizeGeneratedTitleCandidate(summary)

  if (normalizedSummary) {
    rawCandidates.push(normalizedSummary)
    rawCandidates.push(
      ...normalizedSummary
        .split(/[。.!?！？]/u)
        .map((part) => normalizeGeneratedTitleCandidate(part))
    )
  }

  keyTerms.forEach(({ term }) => {
    rawCandidates.push(normalizeGeneratedTitleCandidate(term))
  })

  const seen = new Set<string>()
  const result: string[] = []
  for (const rawCandidate of rawCandidates) {
    if (!rawCandidate || seen.has(rawCandidate)) {
      continue
    }
    seen.add(rawCandidate)
    const candidate = normalizeAutoTitleCandidate(rawCandidate)
    if (!isValidAutoSessionTitleCandidate(candidate)) {
      continue
    }
    result.push(candidate)
    if (result.length >= MAX_AUTO_TITLE_CANDIDATES) {
      break
    }
  }

  return result
}

function getAutoTitleTextPreview(text: string): string {
  const normalized = normalizeGeneratedTitleCandidate(text)
  if (normalized.length <= AUTO_TITLE_DEBUG_PREVIEW_LENGTH) {
    return normalized
  }
  return `${normalized.slice(0, AUTO_TITLE_DEBUG_PREVIEW_LENGTH)}...`
}

function toDebugErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  try {
    return JSON.stringify(error)
  } catch {
    return String(error)
  }
}

function getAutoSessionTitleValidationReasons(title: string): string[] {
  const reasons: string[] = []
  if (title.length < MIN_AUTO_SESSION_TITLE_LENGTH) {
    reasons.push('too_short')
  }
  if (title.length > MAX_AUTO_SESSION_TITLE_LENGTH) {
    reasons.push('too_long')
  }
  if (/\s/u.test(title)) {
    reasons.push('contains_whitespace')
  }
  if (!AUTO_TITLE_SINGLE_WORD_PATTERN.test(title)) {
    reasons.push('invalid_character')
  }
  if (isKnownAutoTitleFallback(title)) {
    reasons.push('known_fallback')
  }
  return reasons
}

function isValidAutoSessionTitleCandidate(title: string): boolean {
  return getAutoSessionTitleValidationReasons(title).length === 0
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

function extractAutoTitleTriggerSessionId(state: unknown): string | null {
  if (!state || typeof state !== 'object') {
    return null
  }
  const candidate = state as { autoTitleSessionId?: unknown }
  if (typeof candidate.autoTitleSessionId !== 'string') {
    return null
  }
  const normalized = candidate.autoTitleSessionId.trim()
  return normalized || null
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

function renameStoredSession(sessionId: string, courseName: string): void {
  const storedSessions = loadStoredSessions()
  if (storedSessions.length === 0) {
    return
  }

  let updated = false
  const nextSessions = storedSessions.map((session) => {
    if (session.session_id !== sessionId) {
      return session
    }
    updated = true
    return {
      ...session,
      course_name: courseName,
    }
  })

  if (updated) {
    saveStoredSessions(nextSessions)
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
  isAutoTitleGenerating: boolean
  autoTitleCandidates: string[]
  onFinalize: (sessionId: string) => Promise<void>
  onDelete: (session: DemoLectureSession) => Promise<void>
  onRename: (sessionId: string, nextTitle: string) => boolean
  onSelectAutoTitleCandidate: (sessionId: string, candidate: string) => void
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
  isAutoTitleGenerating,
  autoTitleCandidates,
  onFinalize,
  onDelete,
  onRename,
  onSelectAutoTitleCandidate,
}: SessionCardProps) {
  const { t } = useTranslation()
  const isBusy = isFinalizing || isDeleting
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [draftTitle, setDraftTitle] = useState(session.course_name)

  const statusLabel =
    session.status === 'live'
      ? t('lectures.status.live')
      : t('lectures.status.ended')

  const handleSaveTitle = useCallback(() => {
    const updated = onRename(session.session_id, draftTitle)
    if (!updated) {
      return
    }
    setIsEditingTitle(false)
  }, [draftTitle, onRename, session.session_id])

  const handleCancelEdit = useCallback(() => {
    setDraftTitle(session.course_name)
    setIsEditingTitle(false)
  }, [session.course_name])

  return (
    <div className="card p-6 space-y-4 hover:shadow-md transition-shadow">
      <div className="space-y-2">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          {isEditingTitle ? (
            <div className="flex-1 space-y-2">
              <input
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                className="input w-full"
                autoFocus
                maxLength={MAX_MANUAL_SESSION_TITLE_LENGTH}
                aria-label={t('lectures.actions.titleInputAria')}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    handleSaveTitle()
                  }
                  if (event.key === 'Escape') {
                    event.preventDefault()
                    handleCancelEdit()
                  }
                }}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn btn-primary min-h-8 px-3 text-xs"
                  onClick={handleSaveTitle}
                >
                  {t('lectures.actions.saveTitle')}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost min-h-8 px-3 text-xs"
                  onClick={handleCancelEdit}
                >
                  {t('lectures.actions.cancelTitle')}
                </button>
              </div>
            </div>
          ) : (
            <h3 className="text-lg font-semibold text-fg-primary line-clamp-2">
              {session.course_name}
            </h3>
          )}
          <div className="flex items-center gap-2 self-end sm:self-start">
            <span className={`badge ${session.status === 'live' ? 'badge-live' : 'badge-muted'}`}>
              {statusLabel}
            </span>
            <button
              type="button"
              className="btn btn-ghost min-h-8 min-w-8 p-1.5 text-fg-secondary"
              aria-label={t('lectures.actions.editSessionTitleAria', { courseName: session.course_name })}
              title={t('lectures.actions.editSessionTitle')}
              onClick={() => {
                if (isEditingTitle) {
                  handleCancelEdit()
                  return
                }
                setDraftTitle(session.course_name)
                setIsEditingTitle(true)
              }}
              disabled={isBusy}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5h2m-9 7h2m4 0h10M7 19h10M4 12h.01M7 5h.01M17 5h.01M4 19h.01M20 12h.01M20 19h.01M14.121 15.536l-3.657 1.22 1.219-3.658 6.86-6.86a1.5 1.5 0 112.121 2.122l-6.543 6.543z" />
              </svg>
            </button>
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
        <Link
          to={`/lectures/${session.session_id}/live`}
          className="btn btn-primary w-full text-center"
        >
          {t('lectures.actions.enter')}
        </Link>
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
        {isAutoTitleGenerating && !isEditingTitle && (
          <p className="text-xs text-fg-secondary">
            {t('lectures.messages.autoTitleRunning')}
          </p>
        )}
        {!isAutoTitleGenerating && autoTitleCandidates.length > 0 && !isEditingTitle && (
          <div className="space-y-2">
            <p className="text-xs text-fg-secondary">
              {t('lectures.messages.autoTitleCandidatesReady')}
            </p>
            <div className="flex flex-wrap gap-2">
              {autoTitleCandidates.map((candidate) => (
                <button
                  key={`${session.session_id}:${candidate}`}
                  type="button"
                  className="btn btn-ghost min-h-8 px-3 text-xs"
                  disabled={isBusy}
                  onClick={() => onSelectAutoTitleCandidate(session.session_id, candidate)}
                  title={candidate}
                >
                  {candidate}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export function LecturesPage() {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const locale: UiLanguage =
    (i18n.resolvedLanguage ?? i18n.language).startsWith('en') ? 'en' : 'ja'
  const autoTitleRequestedSessionIdsRef = useRef<Set<string>>(new Set())
  const manuallyEditedSessionIdsRef = useRef<Set<string>>(new Set())
  const autoTitleDebugLogDisabledSessionIdsRef = useRef<Set<string>>(new Set())
  const autoTitleDebugLogWarnedSessionIdsRef = useRef<Set<string>>(new Set())

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
  const [autoTitleGeneratingSessionIds, setAutoTitleGeneratingSessionIds] =
    useState<Set<string>>(() => new Set())
  const [autoTitleCandidatesBySessionId, setAutoTitleCandidatesBySessionId] =
    useState<Record<string, string[]>>({})
  const [startErrorMessage, setStartErrorMessage] = useState<string | null>(null)

  const filteredSessions = useMemo(() => {
    if (filter === 'all') {
      return sessions
    }
    return sessions.filter((session) => session.status === filter)
  }, [filter, sessions])

  const removeSessionLocally = useCallback((sessionId: string): void => {
    manuallyEditedSessionIdsRef.current.delete(sessionId)
    autoTitleRequestedSessionIdsRef.current.delete(sessionId)
    autoTitleDebugLogDisabledSessionIdsRef.current.delete(sessionId)
    autoTitleDebugLogWarnedSessionIdsRef.current.delete(sessionId)
    setAutoTitleGeneratingSessionIds((prev) => {
      if (!prev.has(sessionId)) {
        return prev
      }
      const next = new Set(prev)
      next.delete(sessionId)
      return next
    })
    setSessions((prev) => {
      const nextSessions = prev.filter((item) => item.session_id !== sessionId)
      saveStoredSessions(nextSessions)
      return nextSessions
    })
    setAutoTitleCandidatesBySessionId((prev) => {
      if (!(sessionId in prev)) {
        return prev
      }
      const next = { ...prev }
      delete next[sessionId]
      return next
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

  const markSessionEndedLocally = useCallback((sessionId: string): void => {
    setSessions((prev) => {
      const nextSessions = prev.map((session) =>
        session.session_id === sessionId
          ? { ...session, status: 'ended' as const }
          : session
      )
      saveStoredSessions(nextSessions)
      return nextSessions
    })
  }, [])

  const markAutoTitleGenerating = useCallback(
    (sessionId: string, isGenerating: boolean): void => {
      setAutoTitleGeneratingSessionIds((prev) => {
        const next = new Set(prev)
        if (isGenerating) {
          next.add(sessionId)
        } else {
          next.delete(sessionId)
        }
        return next
      })
    },
    []
  )

  const setAutoTitleCandidates = useCallback(
    (sessionId: string, candidates: string[]): void => {
      setAutoTitleCandidatesBySessionId((prev) => {
        if (candidates.length === 0) {
          if (!(sessionId in prev)) {
            return prev
          }
          const next = { ...prev }
          delete next[sessionId]
          return next
        }
        return { ...prev, [sessionId]: candidates }
      })
    },
    []
  )

  const sendAutoTitleDebugLog = useCallback(
    async (
      sessionId: string,
      event: string,
      payload: Record<string, unknown>,
      level: AutoTitleDebugLogLevel = 'info'
    ): Promise<void> => {
      if (autoTitleDebugLogDisabledSessionIdsRef.current.has(sessionId)) {
        return
      }

      try {
        await lectureQaApi.logAutoTitleDebug({
          session_id: sessionId,
          event,
          level,
          locale,
          payload,
        })
      } catch (error) {
        const disableLogging =
          error instanceof ApiError && (error.status === 404 || error.status === 0)

        if (!disableLogging) {
          return
        }

        autoTitleDebugLogDisabledSessionIdsRef.current.add(sessionId)
        if (autoTitleDebugLogWarnedSessionIdsRef.current.has(sessionId)) {
          return
        }

        autoTitleDebugLogWarnedSessionIdsRef.current.add(sessionId)
        const reason =
          error.status === 404 ? 'autotitle_log_endpoint_not_found' : 'autotitle_log_network_error'
        console.warn('[auto-title-debug-log] logging disabled for this session.', {
          sessionId,
          reason,
          event,
        })
      }
    },
    [locale]
  )

  const handleRenameSessionTitle = useCallback(
    (sessionId: string, nextTitle: string): boolean => {
      const normalizedTitle = normalizeManualSessionTitle(nextTitle)
      if (!normalizedTitle) {
        showToast({
          variant: 'warning',
          title: t('lectures.messages.sessionTitleEmpty'),
        })
        return false
      }

      const currentTitle = sessions.find((session) => session.session_id === sessionId)?.course_name
      if (currentTitle === normalizedTitle) {
        return true
      }

      manuallyEditedSessionIdsRef.current.add(sessionId)
      markAutoTitleGenerating(sessionId, false)
      setAutoTitleCandidates(sessionId, [])
      renameStoredSession(sessionId, normalizedTitle)
      renameSessionLocally(sessionId, normalizedTitle)
      void sendAutoTitleDebugLog(
        sessionId,
        'auto_title.manual_rename',
        {
          title: normalizedTitle,
          title_length: normalizedTitle.length,
        }
      )
      showToast({
        variant: 'success',
        title: t('lectures.messages.sessionTitleUpdated'),
        message: normalizedTitle,
      })
      return true
    },
    [
      markAutoTitleGenerating,
      renameSessionLocally,
      sendAutoTitleDebugLog,
      sessions,
      setAutoTitleCandidates,
      showToast,
      t,
    ]
  )

  const handleSelectAutoTitleCandidate = useCallback(
    (sessionId: string, candidate: string): void => {
      void handleRenameSessionTitle(sessionId, candidate)
    },
    [handleRenameSessionTitle]
  )

  const updateSessionTitleFromQa = useCallback(
    async (sessionId: string): Promise<void> => {
      const langMode: LectureQaLangMode = locale === 'en' ? 'en' : 'ja'
      const defaultTitle = AUTO_TITLE_DEFAULT_LABELS[locale]
      const shouldSkipTitleUpdate = (): boolean =>
        manuallyEditedSessionIdsRef.current.has(sessionId)
      const collectedCandidates: string[] = []
      const appendCandidate = (
        candidate: string
      ): {
        accepted: boolean
        normalized: string
        reason: string
        validationReasons: string[]
      } => {
        const normalized = normalizeAutoTitleCandidate(candidate)
        if (!normalized) {
          return {
            accepted: false,
            normalized,
            reason: 'empty',
            validationReasons: ['empty'],
          }
        }
        const validationReasons = getAutoSessionTitleValidationReasons(normalized)
        if (validationReasons.length > 0) {
          return {
            accepted: false,
            normalized,
            reason: 'invalid',
            validationReasons,
          }
        }
        if (collectedCandidates.includes(normalized)) {
          return {
            accepted: false,
            normalized,
            reason: 'duplicate',
            validationReasons: ['duplicate'],
          }
        }
        collectedCandidates.push(normalized)
        return {
          accepted: true,
          normalized,
          reason: '',
          validationReasons: [],
        }
      }
      const hasGroundingSources = (sources: readonly unknown[]): boolean =>
        sources.length > 0
      const isKnownFallbackResponse = (params: {
        answer: string
        fallback: string | null
      }): boolean =>
        isKnownAutoTitleFallbackMessage(params.answer) ||
        isKnownAutoTitleFallbackMessage(params.fallback)
      const logDebug = (
        event: string,
        payload: Record<string, unknown>,
        level: AutoTitleDebugLogLevel = 'info'
      ): void => {
        void sendAutoTitleDebugLog(sessionId, event, payload, level)
      }
      const judgeCandidateWithLlm = async (
        candidate: string,
        slot: number,
        attempt: number
      ): Promise<{
        accepted: boolean
        verdict: AutoTitleJudgeVerdict
        reason: string
      }> => {
        try {
          const judgeResponse = await lectureQaApi.ask({
            session_id: sessionId,
            question: buildAutoTitleJudgePrompt({
              locale,
              candidate,
            }),
            lang_mode: langMode,
            retrieval_mode: 'source-plus-context',
            top_k: AUTO_TITLE_QA_TOP_K,
            context_window: AUTO_TITLE_QA_CONTEXT_WINDOW,
          })
          const verdict = parseAutoTitleJudgeVerdict(judgeResponse.answer)
          const knownFallback = isKnownFallbackResponse({
            answer: judgeResponse.answer,
            fallback: judgeResponse.fallback,
          })
          const hasSources = hasGroundingSources(judgeResponse.sources)
          const accepted = verdict !== 'ng'
          const reason =
            verdict === 'ng'
              ? 'judge_ng_explicit'
              : verdict === 'ok'
                ? 'judge_ok'
                : knownFallback
                  ? 'judge_inconclusive_known_fallback'
                  : hasSources
                    ? 'judge_inconclusive_unparsable'
                    : 'judge_inconclusive_no_sources'

          logDebug('judge.response', {
            slot,
            attempt,
            candidate,
            candidate_length: candidate.length,
            fallback: judgeResponse.fallback ?? '',
            fallback_known: knownFallback,
            sources_count: judgeResponse.sources.length,
            answer_known_fallback: isKnownAutoTitleFallbackMessage(judgeResponse.answer),
            answer_preview: getAutoTitleTextPreview(judgeResponse.answer),
            answer_length: normalizeGeneratedTitleCandidate(judgeResponse.answer).length,
            verdict,
            accepted,
            reason,
          })
          return { accepted, verdict, reason }
        } catch (error) {
          logDebug(
            'judge.request.error',
            {
              slot,
              attempt,
              candidate,
              error: toDebugErrorMessage(error),
              reason: 'judge_inconclusive_error',
            },
            'warning'
          )
          return {
            accepted: true,
            verdict: 'inconclusive',
            reason: 'judge_inconclusive_error',
          }
        }
      }

      try {
        logDebug('auto_title.start', {
          lang_mode: langMode,
          max_candidates: MAX_AUTO_TITLE_CANDIDATES,
          max_attempts_per_slot: MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS,
        })

        try {
          await lectureQaApi.buildIndex({
            session_id: sessionId,
            rebuild: false,
          })
          logDebug('index.build.success', {})
        } catch (error) {
          logDebug(
            'index.build.error',
            {
              error: toDebugErrorMessage(error),
            },
            'warning'
          )
        }

        for (let slot = 0; slot < MAX_AUTO_TITLE_CANDIDATES; slot += 1) {
          if (shouldSkipTitleUpdate()) {
            logDebug(
              'auto_title.skip',
              {
                reason: 'manually_edited',
                phase: 'generation',
              },
              'warning'
            )
            return
          }

          let accepted = false
          for (
            let attempt = 0;
            attempt < MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS;
            attempt += 1
          ) {
            if (shouldSkipTitleUpdate()) {
              logDebug(
                'auto_title.skip',
                {
                  reason: 'manually_edited',
                  phase: 'retry_loop',
                  slot: slot + 1,
                  attempt: attempt + 1,
                },
                'warning'
              )
              return
            }

            try {
              logDebug('generate.request.start', {
                slot: slot + 1,
                attempt: attempt + 1,
                excluded_candidates: [...collectedCandidates],
              })

              const response = await lectureQaApi.ask({
                session_id: sessionId,
                question: buildAutoTitleSingleWordPrompt({
                  locale,
                  excludedCandidates: collectedCandidates,
                }),
                lang_mode: langMode,
                retrieval_mode: 'source-plus-context',
                top_k: AUTO_TITLE_QA_TOP_K,
                context_window: AUTO_TITLE_QA_CONTEXT_WINDOW,
              })

              const knownFallback = isKnownFallbackResponse({
                answer: response.answer,
                fallback: response.fallback,
              })
              const hasSources = hasGroundingSources(response.sources)
              logDebug('generate.response', {
                slot: slot + 1,
                attempt: attempt + 1,
                fallback: response.fallback ?? '',
                fallback_known: knownFallback,
                sources_count: response.sources.length,
                answer_known_fallback: isKnownAutoTitleFallbackMessage(response.answer),
                answer_preview: getAutoTitleTextPreview(response.answer),
                answer_length: normalizeGeneratedTitleCandidate(response.answer).length,
              })

              if (!hasSources) {
                logDebug(
                  'candidate.rejected',
                  {
                    slot: slot + 1,
                    attempt: attempt + 1,
                    reason: 'no_sources',
                  },
                  'warning'
                )
                if (attempt + 1 < MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS) {
                  await waitForAutoTitleRetry()
                }
                continue
              }
              if (knownFallback) {
                logDebug(
                  'candidate.rejected',
                  {
                    slot: slot + 1,
                    attempt: attempt + 1,
                    reason: 'known_fallback',
                  },
                  'warning'
                )
                if (attempt + 1 < MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS) {
                  await waitForAutoTitleRetry()
                }
                continue
              }

              const candidate = extractAutoTitleWordFromQaAnswer(response.answer)
              const appendResult = appendCandidate(candidate)
              if (!appendResult.accepted) {
                logDebug(
                  'candidate.rejected',
                  {
                    slot: slot + 1,
                    attempt: attempt + 1,
                    reason: appendResult.reason,
                    raw_candidate_preview: getAutoTitleTextPreview(candidate),
                    normalized_candidate: appendResult.normalized,
                    normalized_length: appendResult.normalized.length,
                    validation_reasons: appendResult.validationReasons,
                  },
                  'warning'
                )
                if (attempt + 1 < MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS) {
                  await waitForAutoTitleRetry()
                }
                continue
              }

              const judgeResult = await judgeCandidateWithLlm(
                appendResult.normalized,
                slot + 1,
                attempt + 1
              )
              if (!judgeResult.accepted) {
                collectedCandidates.pop()
                logDebug(
                  'candidate.rejected',
                  {
                    slot: slot + 1,
                    attempt: attempt + 1,
                    reason: judgeResult.reason,
                    judge_verdict: judgeResult.verdict,
                    normalized_candidate: appendResult.normalized,
                    normalized_length: appendResult.normalized.length,
                  },
                  'warning'
                )
                if (attempt + 1 < MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS) {
                  await waitForAutoTitleRetry()
                }
                continue
              }

              logDebug('candidate.accepted', {
                slot: slot + 1,
                attempt: attempt + 1,
                candidate: appendResult.normalized,
                candidate_length: appendResult.normalized.length,
                total_candidates: collectedCandidates.length,
              })
              accepted = true
              break
            } catch (error) {
              logDebug(
                'generate.request.error',
                {
                  slot: slot + 1,
                  attempt: attempt + 1,
                  error: toDebugErrorMessage(error),
                },
                'warning'
              )
              if (attempt + 1 < MAX_AUTO_SESSION_TITLE_RETRY_ATTEMPTS) {
                await waitForAutoTitleRetry()
              }
            }
          }

          if (!accepted) {
            logDebug(
              'slot.exhausted',
              {
                slot: slot + 1,
                collected_candidates: [...collectedCandidates],
              },
              'warning'
            )
            break
          }
        }

        if (shouldSkipTitleUpdate()) {
          logDebug(
            'auto_title.skip',
            {
              reason: 'manually_edited',
              phase: 'after_generation',
            },
            'warning'
          )
          return
        }

        try {
          logDebug('summary.fallback.start', {
            collected_candidates: [...collectedCandidates],
          })
          const latestSummary = await demoApi.getLatestSummary(sessionId)
          if (latestSummary.status === 'ok') {
            buildAutoTitleFromSummary({
              summary: latestSummary.summary,
              keyTerms: latestSummary.key_terms,
            }).forEach((candidate) => {
              const result = appendCandidate(candidate)
              if (!result.accepted) {
                void logDebug(
                  'summary.candidate.rejected',
                  {
                    reason: result.reason,
                    candidate_preview: getAutoTitleTextPreview(candidate),
                    normalized_candidate: result.normalized,
                    validation_reasons: result.validationReasons,
                  },
                  'warning'
                )
                return
              }
              void logDebug('summary.candidate.accepted', {
                candidate: result.normalized,
                candidate_length: result.normalized.length,
                total_candidates: collectedCandidates.length,
              })
            })
          } else {
            logDebug(
              'summary.fallback.no_data',
              {
                summary_status: latestSummary.status,
              },
              'warning'
            )
          }
        } catch (error) {
          logDebug(
            'summary.fallback.error',
            {
              error: toDebugErrorMessage(error),
            },
            'warning'
          )
        }

        if (shouldSkipTitleUpdate()) {
          logDebug(
            'auto_title.skip',
            {
              reason: 'manually_edited',
              phase: 'before_finalize',
            },
            'warning'
          )
          return
        }

        if (collectedCandidates.length > 0) {
          const candidates = collectedCandidates.slice(0, MAX_AUTO_TITLE_CANDIDATES)
          setAutoTitleCandidates(sessionId, candidates)
          logDebug('auto_title.candidates.ready', {
            candidates,
            candidate_count: candidates.length,
          })
          showToast({
            variant: 'info',
            title: t('lectures.messages.autoTitleCandidatesReady'),
          })
          return
        }

        setAutoTitleCandidates(sessionId, [])
        renameStoredSession(sessionId, defaultTitle)
        renameSessionLocally(sessionId, defaultTitle)
        logDebug(
          'auto_title.default_restored',
          {
            default_title: defaultTitle,
          },
          'warning'
        )
        showToast({
          variant: 'warning',
          title: t('lectures.messages.autoTitleRestoreDefault'),
        })
      } catch (error) {
        logDebug(
          'auto_title.unhandled_error',
          {
            error: toDebugErrorMessage(error),
          },
          'error'
        )
        if (!shouldSkipTitleUpdate()) {
          setAutoTitleCandidates(sessionId, [])
          renameStoredSession(sessionId, defaultTitle)
          renameSessionLocally(sessionId, defaultTitle)
          showToast({
            variant: 'warning',
            title: t('lectures.messages.autoTitleRestoreDefault'),
          })
        }
      } finally {
        logDebug('auto_title.end', {
          collected_candidates: [...collectedCandidates],
          collected_count: collectedCandidates.length,
          manually_edited: shouldSkipTitleUpdate(),
        })
        markAutoTitleGenerating(sessionId, false)
      }
    },
    [
      locale,
      markAutoTitleGenerating,
      renameSessionLocally,
      sendAutoTitleDebugLog,
      setAutoTitleCandidates,
      showToast,
      t,
    ]
  )

  useEffect(() => {
    const sessionId = extractAutoTitleTriggerSessionId(location.state)
    if (!sessionId) {
      return
    }

    const clearLocationState = (): void => {
      navigate(`${location.pathname}${location.search}`, {
        replace: true,
        state: null,
      })
    }

    if (autoTitleRequestedSessionIdsRef.current.has(sessionId)) {
      void sendAutoTitleDebugLog(
        sessionId,
        'auto_title.trigger.skip',
        {
          reason: 'already_requested',
        },
        'warning'
      )
      clearLocationState()
      return
    }

    const targetSession = sessions.find((session) => session.session_id === sessionId)
    if (!targetSession) {
      void sendAutoTitleDebugLog(
        sessionId,
        'auto_title.trigger.skip',
        {
          reason: 'session_not_found',
        },
        'warning'
      )
      clearLocationState()
      return
    }
    if (targetSession.status !== 'live') {
      void sendAutoTitleDebugLog(
        sessionId,
        'auto_title.trigger.skip',
        {
          reason: 'session_not_live',
          status: targetSession.status,
        },
        'warning'
      )
      clearLocationState()
      return
    }
    if (!isPlaceholderSessionTitle(targetSession.course_name)) {
      void sendAutoTitleDebugLog(
        sessionId,
        'auto_title.trigger.skip',
        {
          reason: 'title_not_placeholder',
          title: targetSession.course_name,
        },
        'warning'
      )
      clearLocationState()
      return
    }

    autoTitleRequestedSessionIdsRef.current.add(sessionId)
    manuallyEditedSessionIdsRef.current.delete(sessionId)
    markAutoTitleGenerating(sessionId, true)
    setAutoTitleCandidates(sessionId, [])
    renameSessionLocally(sessionId, AUTO_TITLE_GENERATING_LABELS[locale])
    void sendAutoTitleDebugLog(sessionId, 'auto_title.trigger.start', {
      locale,
      current_title: targetSession.course_name,
    })
    void updateSessionTitleFromQa(sessionId)
    clearLocationState()
  }, [
    location.pathname,
    location.search,
    location.state,
    locale,
    markAutoTitleGenerating,
    navigate,
    renameSessionLocally,
    sendAutoTitleDebugLog,
    setAutoTitleCandidates,
    sessions,
    updateSessionTitleFromQa,
  ])

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

    setFinalizingSessionIds((prev) => new Set(prev).add(sessionId))
    try {
      await demoApi.finalizeDemoSession(sessionId)
      markSessionEndedLocally(sessionId)
      showToast({
        variant: 'success',
        title: t('lectures.messages.sessionFinalized'),
      })
    } catch (error) {
      const apiErr = error as { status?: number }
      if (apiErr?.status === 409) {
        markSessionEndedLocally(sessionId)
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
        <h1 className="mb-2 text-3xl font-bold text-fg-primary">{t('lectures.title')}</h1>
        <p className="text-fg-secondary">
          {hasSessions
            ? t('lectures.pageDescription.withSessions')
            : t('lectures.pageDescription.withoutSessions')}
        </p>
      </div>

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <button
          type="button"
          onClick={handleStartSession}
          disabled={isStarting}
          className="btn btn-primary w-full sm:w-auto"
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
          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap" role="group" aria-label={t('lectures.filters.ariaLabel')}>
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={`btn w-full sm:w-auto ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}
              aria-pressed={filter === 'all'}
            >
              {t('lectures.filters.all')}
            </button>
            <button
              type="button"
              onClick={() => setFilter('live')}
              className={`btn w-full sm:w-auto ${filter === 'live' ? 'btn-primary' : 'btn-ghost'}`}
              aria-pressed={filter === 'live'}
            >
              {t('lectures.filters.live')}
            </button>
            <button
              type="button"
              onClick={() => setFilter('ended')}
              className={`btn w-full sm:w-auto ${filter === 'ended' ? 'btn-primary' : 'btn-ghost'}`}
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
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {filteredSessions.map((session) => (
                <SessionCard
                  key={session.session_id}
                  session={session}
                  locale={locale}
                  isFinalizing={finalizingSessionIds.has(session.session_id)}
                  isDeleting={deletingSessionIds.has(session.session_id)}
                  isAutoTitleGenerating={autoTitleGeneratingSessionIds.has(session.session_id)}
                  autoTitleCandidates={autoTitleCandidatesBySessionId[session.session_id] ?? []}
                  onFinalize={handleFinalizeSession}
                  onDelete={handleDeleteSession}
                  onRename={handleRenameSessionTitle}
                  onSelectAutoTitleCandidate={handleSelectAutoTitleCandidate}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
