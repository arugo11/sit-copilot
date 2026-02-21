/**
 * API Client
 * Base API client for backend communication
 */

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured === 'string') {
    return configured.trim().replace(/\/+$/, '')
  }
  // In dev, prefer same-origin + Vite proxy to avoid CORS setup.
  if (import.meta.env.DEV) {
    return ''
  }
  return 'http://localhost:8000'
}

export const API_BASE_URL = resolveApiBaseUrl()
export const LECTURE_API_TOKEN =
  import.meta.env.VITE_LECTURE_API_TOKEN || 'dev-lecture-token'
export const DEMO_USER_ID = import.meta.env.VITE_DEMO_USER_ID || 'demo-user'

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

export interface ReadinessCheckRequest {
  course_name: string
  syllabus_text: string
  lang_mode: 'ja' | 'easy-ja' | 'en'
}

export interface ReadinessCheckResponse {
  readiness_score: number
}

export interface HealthResponse {
  status: string
  version: string
}

interface SummaryKeyTerm {
  term: string
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
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    const headers = new Headers(options.headers ?? {})
    headers.set('Content-Type', 'application/json')
    headers.set('X-Lecture-Token', LECTURE_API_TOKEN)
    headers.set('X-User-Id', DEMO_USER_ID)

    const config: RequestInit = {
      ...options,
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
          message =
            'Unauthorized. デモトークン設定を確認してください (X-Lecture-Token / X-User-Id)。'
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

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }
}

export const apiClient = new ApiClient()

/**
 * Demo API
 */
export const demoApi = {
  async startDemoSession(
    request: LectureSessionStartRequest
  ): Promise<LectureSessionStartResponse> {
    return apiClient.post<LectureSessionStartResponse>(
      '/api/v4/lecture/session/start',
      request
    )
  },

  async finalizeDemoSession(sessionId: string): Promise<LectureSessionFinalizeResponse> {
    return apiClient.post<LectureSessionFinalizeResponse>(
      '/api/v4/lecture/session/finalize',
      {
        session_id: sessionId,
        build_qa_index: false,
      }
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

  async getLatestSummary(sessionId: string): Promise<LectureSummaryLatestResponse> {
    return apiClient.get<LectureSummaryLatestResponse>(
      `/api/v4/lecture/summary/latest?session_id=${encodeURIComponent(sessionId)}`
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
