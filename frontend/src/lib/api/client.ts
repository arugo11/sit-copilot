/**
 * API Client
 * Base API client for backend communication
 */

import i18n from '@/lib/i18n'

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured === 'string') {
    return configured.trim().replace(/\/+$/, '')
  }
  // In dev, prefer same-origin + Vite proxy to avoid CORS setup.
  if (import.meta.env.DEV) {
    return ''
  }
  return 'http://127.0.0.1:8000'
}

export const API_BASE_URL = resolveApiBaseUrl()
export const LECTURE_API_TOKEN =
  import.meta.env.VITE_LECTURE_API_TOKEN || 'dev-lecture-token'
export const PROCEDURE_API_TOKEN =
  import.meta.env.VITE_PROCEDURE_API_TOKEN || 'dev-procedure-token'
export const DEMO_USER_ID = import.meta.env.VITE_DEMO_USER_ID || 'demo_user'

export class ApiError extends Error {
  status: number
  details?: unknown

  constructor(status: number, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export interface UserSettings {
  theme?: 'light' | 'dark' | 'high-contrast'
  language?: 'ja' | 'en'
  fontSize?: 'small' | 'normal' | 'large'
  reducedMotion?: boolean
  transcriptDensity?: 'comfortable' | 'compact'
  autoScrollDefault?: boolean
}

interface SettingsResponsePayload {
  user_id: string
  settings: Record<string, unknown>
  updated_at: string | null
}

export interface LectureSessionStartRequest {
  course_name: string
  course_id?: string
  lang_mode?: 'ja' | 'easy-ja' | 'en'
  camera_enabled: boolean
  consent_acknowledged: boolean
}

export interface LectureSessionStartResponse {
  session_id: string
  status: 'active'
}

export interface LectureSessionFinalizeResponse {
  session_id: string
  status: 'finalized'
}

export interface LectureSessionDeleteResponse {
  session_id: string
  status: 'deleted'
  auto_finalized: boolean
}

export interface SpeechChunkIngestRequest {
  session_id: string
  start_ms: number
  end_ms: number
  text: string
  confidence: number
  is_final: boolean
  speaker: 'teacher' | 'student'
}

export interface SpeechChunkIngestResponse {
  event_id: string
  session_id: string
  accepted: boolean
}

export interface SpeechChunkAuditApplyRequest {
  session_id: string
  event_id: string
}

export interface SpeechChunkAuditApplyResponse {
  session_id: string
  event_id: string
  original_text: string
  corrected_text: string
  updated: boolean
  review_status: 'reviewed' | 'review_failed'
  reviewed: boolean
  was_corrected: boolean
  retry_count: number
  failure_reason?: string | null
}

export interface SubtitleTransformRequest {
  session_id: string
  text: string
  target_lang_mode: 'ja' | 'easy-ja' | 'en'
}

export interface SubtitleTransformResponse {
  session_id: string
  target_lang_mode: 'ja' | 'easy-ja' | 'en'
  transformed_text: string
  status: 'translated' | 'fallback' | 'passthrough'
  fallback_reason?: string | null
}

export interface SubtitleAuditRequest {
  session_id: string
  text: string
}

export interface SubtitleAuditResponse {
  session_id: string
  original_text: string
  corrected_text: string
  review_status: 'reviewed' | 'review_failed'
  reviewed: boolean
  was_corrected: boolean
  retry_count: number
  failure_reason?: string | null
}

export interface ReadinessCheckRequest {
  course_name: string
  syllabus_text: string
  first_material_blob_path?: string | null
  lang_mode?: 'ja' | 'easy-ja' | 'en'
  jp_level_self?: number | null
  domain_level_self?: number | null
}

export interface ReadinessTerm {
  term: string
  explanation: string
}

export interface ReadinessCheckResponse {
  readiness_score: number
  terms: ReadinessTerm[]
  difficult_points: string[]
  recommended_settings: string[]
  prep_tasks: string[]
  disclaimer: string
}

export interface HealthResponse {
  status: string
  version: string
}

interface SummaryKeyTerm {
  term: string
  explanation?: string
  translation?: string
}

export interface LectureSummaryLatestResponse {
  session_id: string
  window_start_ms: number
  window_end_ms: number
  summary: string
  key_terms: SummaryKeyTerm[]
  status: 'ok' | 'no_data'
}

export type LectureQaLangMode = 'ja' | 'easy-ja' | 'en'
export type LectureQaConfidence = 'high' | 'medium' | 'low'
export type LectureQaRetrievalMode = 'source-only' | 'source-plus-context'
export type LectureQaSourceType = 'speech' | 'visual'
export type AutoTitleDebugLogLevel = 'info' | 'warning' | 'error'
export type AutoTitleDebugLocale = 'ja' | 'en'

export interface LectureSource {
  chunk_id: string
  type: LectureQaSourceType
  text: string
  timestamp: string | null
  start_ms: number | null
  end_ms: number | null
  speaker: string | null
  bm25_score: number
  is_direct_hit: boolean
}

export interface LectureAskRequest {
  session_id: string
  question: string
  lang_mode: LectureQaLangMode
  retrieval_mode: LectureQaRetrievalMode
  top_k: number
  context_window: number
}

export interface LectureAskResponse {
  answer: string
  confidence: LectureQaConfidence
  sources: LectureSource[]
  verification_summary: string | null
  action_next: string
  fallback: string | null
}

export interface LectureFollowupRequest extends LectureAskRequest {
  history_turns: number
}

export interface LectureFollowupResponse extends LectureAskResponse {
  resolved_query: string
}

export interface LectureIndexBuildRequest {
  session_id: string
  rebuild?: boolean
}

export interface LectureIndexBuildResponse {
  index_version: string
  chunk_count: number
  built_at: string
  status: 'success' | 'skipped'
}

export interface LectureAutoTitleDebugLogRequest {
  session_id: string
  event: string
  level?: AutoTitleDebugLogLevel
  locale: AutoTitleDebugLocale
  payload?: Record<string, unknown>
}

export interface LectureAutoTitleDebugLogResponse {
  status: 'logged'
  log_file: string
}

export type ProcedureQaLangMode = 'ja' | 'easy-ja' | 'en'
export type ProcedureQaConfidence = 'high' | 'medium' | 'low'

export interface ProcedureSource {
  title: string
  section: string
  snippet: string
  source_id: string
}

export interface ProcedureAskRequest {
  query: string
  lang_mode: ProcedureQaLangMode
}

export interface ProcedureAskResponse {
  answer: string
  confidence: ProcedureQaConfidence
  sources: ProcedureSource[]
  action_next: string
  fallback: string
}

type AuthScope = 'lecture' | 'procedure' | 'none'

interface ApiRequestOptions extends RequestInit {
  authScope?: AuthScope
}

function isEnglishUi(): boolean {
  const language = i18n.resolvedLanguage ?? i18n.language
  return language.startsWith('en')
}

export function getUnauthorizedMessage(scope: 'lecture' | 'procedure'): string {
  if (scope === 'procedure') {
    return isEnglishUi()
      ? 'Unauthorized. Check token settings (X-Procedure-Token).'
      : 'Unauthorized. トークン設定を確認してください (X-Procedure-Token)。'
  }
  return isEnglishUi()
    ? 'Unauthorized. Check token settings (X-Lecture-Token / X-User-Id).'
    : 'Unauthorized. トークン設定を確認してください (X-Lecture-Token / X-User-Id)。'
}

function normalizeUserSettings(value: unknown): UserSettings {
  if (!value || typeof value !== 'object') {
    return {}
  }
  const settings = value as Record<string, unknown>
  const normalized: UserSettings = {}

  if (settings.theme === 'light' || settings.theme === 'dark' || settings.theme === 'high-contrast') {
    normalized.theme = settings.theme
  }
  if (settings.language === 'ja' || settings.language === 'en') {
    normalized.language = settings.language
  }
  if (settings.fontSize === 'small' || settings.fontSize === 'normal' || settings.fontSize === 'large') {
    normalized.fontSize = settings.fontSize
  }
  if (typeof settings.reducedMotion === 'boolean') {
    normalized.reducedMotion = settings.reducedMotion
  }
  if (settings.transcriptDensity === 'comfortable' || settings.transcriptDensity === 'compact') {
    normalized.transcriptDensity = settings.transcriptDensity
  }
  if (typeof settings.autoScrollDefault === 'boolean') {
    normalized.autoScrollDefault = settings.autoScrollDefault
  }

  return normalized
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return isEnglishUi()
        ? 'Network error: cannot reach API server. Check backend startup and VITE_API_BASE_URL.'
        : 'Network error: APIサーバーに接続できません。バックエンド起動と VITE_API_BASE_URL を確認してください。'
    }
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return fallback
}

/**
 * Base API client with error handling
 */
class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: ApiRequestOptions = {}
  ): Promise<T> {
    const { authScope = 'lecture', ...fetchOptions } = options
    const url = `${this.baseUrl}${endpoint}`

    const headers = new Headers(fetchOptions.headers ?? {})
    headers.set('Content-Type', 'application/json')

    if (authScope === 'lecture') {
      headers.set('X-Lecture-Token', LECTURE_API_TOKEN)
      headers.set('X-User-Id', DEMO_USER_ID)
    }

    if (authScope === 'procedure') {
      headers.set('X-Procedure-Token', PROCEDURE_API_TOKEN)
    }

    const config: RequestInit = {
      ...fetchOptions,
      headers,
    }

    try {
      const response = await fetch(url, config)

      if (!response.ok) {
        let message = 'API request failed'
        try {
          const errorPayload = await response.json() as {
            message?: string
            detail?: string
          }
          message = errorPayload.message || errorPayload.detail || message
        } catch {
          message = response.statusText || message
        }
        if (response.status === 401) {
          message = getUnauthorizedMessage(
            authScope === 'procedure' ? 'procedure' : 'lecture'
          )
        }
        throw new ApiError(response.status, message)
      }

      return response.json()
    } catch (error) {
      if (error instanceof ApiError) {
        throw error
      }
      throw new ApiError(0, 'Network error', error)
    }
  }

  async get<T>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' })
  }

  async post<T>(endpoint: string, data?: unknown, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async patch<T>(endpoint: string, data?: unknown, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' })
  }
}

export const apiClient = new ApiClient()

async function waitMs(ms: number): Promise<void> {
  await new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function isTransientSessionError(error: unknown): boolean {
  if (!(error instanceof ApiError)) {
    return false
  }
  return error.status === 0 || error.status === 503
}

async function withSessionRetry<T>(operation: () => Promise<T>): Promise<T> {
  const delays = [250, 700]
  let lastError: unknown

  for (let attempt = 0; attempt <= delays.length; attempt += 1) {
    try {
      return await operation()
    } catch (error) {
      lastError = error
      if (!isTransientSessionError(error) || attempt >= delays.length) {
        throw error
      }
      await waitMs(delays[attempt])
    }
  }

  throw lastError
}

/**
 * Demo API
 */
export const demoApi = {
  async startDemoSession(
    request: LectureSessionStartRequest
  ): Promise<LectureSessionStartResponse> {
    return withSessionRetry(() =>
      apiClient.post<LectureSessionStartResponse>(
        '/api/v4/lecture/session/start',
        request
      )
    )
  },

  async finalizeDemoSession(sessionId: string): Promise<LectureSessionFinalizeResponse> {
    return withSessionRetry(() =>
      apiClient.post<LectureSessionFinalizeResponse>(
        '/api/v4/lecture/session/finalize',
        {
          session_id: sessionId,
          build_qa_index: false,
        }
      )
    )
  },

  async deleteDemoSession(sessionId: string): Promise<LectureSessionDeleteResponse> {
    return withSessionRetry(() =>
      apiClient.delete<LectureSessionDeleteResponse>(
        `/api/v4/lecture/session/${encodeURIComponent(sessionId)}`
      )
    )
  },

  async checkReadiness(
    request: ReadinessCheckRequest
  ): Promise<ReadinessCheckResponse> {
    return apiClient.post<ReadinessCheckResponse>(
      '/api/v4/course/readiness/check',
      request
    )
  },

  async ingestSpeechChunk(
    request: SpeechChunkIngestRequest
  ): Promise<SpeechChunkIngestResponse> {
    return apiClient.post<SpeechChunkIngestResponse>(
      '/api/v4/lecture/speech/chunk',
      request
    )
  },

  async auditAndApplySpeechChunk(
    request: SpeechChunkAuditApplyRequest
  ): Promise<SpeechChunkAuditApplyResponse> {
    return apiClient.post<SpeechChunkAuditApplyResponse>(
      '/api/v4/lecture/speech/chunk/audit-apply',
      request
    )
  },

  async getLatestSummary(sessionId: string): Promise<LectureSummaryLatestResponse> {
    return apiClient.get<LectureSummaryLatestResponse>(
      `/api/v4/lecture/summary/latest?session_id=${encodeURIComponent(sessionId)}`
    )
  },

  async analyzeKeyterms(request: {
    session_id: string
    transcript_text: string
    lang_mode: 'ja' | 'easy-ja' | 'en'
  }): Promise<{ key_terms: SummaryKeyTerm[]; detected_terms: string[] }> {
    return apiClient.post<{ key_terms: SummaryKeyTerm[]; detected_terms: string[] }>(
      '/api/v4/lecture/transcript/analyze-keyterms',
      request
    )
  },

  async updateLangMode(request: {
    session_id: string
    lang_mode: 'ja' | 'easy-ja' | 'en'
  }): Promise<{ session_id: string; lang_mode: string; status: string }> {
    return apiClient.patch<{ session_id: string; lang_mode: string; status: string }>(
      '/api/v4/lecture/session/lang-mode',
      request
    )
  },

  async transformSubtitle(
    request: SubtitleTransformRequest
  ): Promise<SubtitleTransformResponse> {
    return apiClient.post<SubtitleTransformResponse>(
      '/api/v4/lecture/subtitle/transform',
      request
    )
  },

  async auditSubtitle(
    request: SubtitleAuditRequest
  ): Promise<SubtitleAuditResponse> {
    return apiClient.post<SubtitleAuditResponse>(
      '/api/v4/lecture/subtitle/audit',
      request
    )
  },
}

/**
 * Lecture QA API
 */
export const lectureQaApi = {
  async buildIndex(
    request: LectureIndexBuildRequest
  ): Promise<LectureIndexBuildResponse> {
    return apiClient.post<LectureIndexBuildResponse>(
      '/api/v4/lecture/qa/index/build',
      {
        session_id: request.session_id,
        rebuild: request.rebuild ?? false,
      }
    )
  },

  async ask(request: LectureAskRequest): Promise<LectureAskResponse> {
    return apiClient.post<LectureAskResponse>('/api/v4/lecture/qa/ask', request)
  },

  async logAutoTitleDebug(
    request: LectureAutoTitleDebugLogRequest
  ): Promise<LectureAutoTitleDebugLogResponse> {
    return apiClient.post<LectureAutoTitleDebugLogResponse>(
      '/api/v4/lecture/qa/autotitle/log',
      {
        session_id: request.session_id,
        event: request.event,
        level: request.level ?? 'info',
        locale: request.locale,
        payload: request.payload ?? {},
      }
    )
  },

  async followup(
    request: LectureFollowupRequest
  ): Promise<LectureFollowupResponse> {
    return apiClient.post<LectureFollowupResponse>(
      '/api/v4/lecture/qa/followup',
      request
    )
  },
}

/**
 * Procedure QA API
 */
export const procedureQaApi = {
  async ask(request: ProcedureAskRequest): Promise<ProcedureAskResponse> {
    return apiClient.post<ProcedureAskResponse>(
      '/api/v4/procedure/ask',
      request,
      { authScope: 'procedure' }
    )
  },
}

/**
 * Settings API
 */
export const settingsApi = {
  async get(): Promise<UserSettings> {
    const payload = await apiClient.get<SettingsResponsePayload>('/api/v4/settings/me')
    return normalizeUserSettings(payload.settings)
  },

  async update(settings: UserSettings): Promise<UserSettings> {
    const payload = await apiClient.post<SettingsResponsePayload>(
      '/api/v4/settings/me',
      { settings }
    )
    return normalizeUserSettings(payload.settings)
  },
}

/**
 * Health Check API
 */
export const healthApi = {
  async check(): Promise<HealthResponse> {
    return apiClient.get<HealthResponse>('/api/v4/health')
  },
}
