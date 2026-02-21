/**
 * API Client
 * Base API client for backend communication
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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

export interface Lecture {
  lectureId: string
  title: string
  instructor: string
  room: string
  startAt: string
  endAt: string
  status: 'upcoming' | 'live' | 'ended'
  languageTags: string[]
  accessibilityTags: string[]
  lastSummary?: string
}

export interface QaRequest {
  question: string
  answerLanguage: 'ja' | 'en'
  answerStyle: 'short' | 'normal' | 'detailed'
  scope: 'whole_lecture' | 'current_topic' | 'selected_range'
  selectedRange?: { fromMs: number; toMs: number }
}

export interface QaAnswer {
  answerId: string
  status: 'streaming' | 'done' | 'error'
  markdown: string
  citations: Array<{
    citationId: string
    type: 'audio' | 'slide' | 'board' | 'ocr'
    label: string
    tsStartMs?: number
    tsEndMs?: number
    sourceFrameId?: string
  }>
  followups: string[]
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

    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    }

    try {
      const response = await fetch(url, config)

      if (!response.ok) {
        let message = 'API request failed'
        try {
          const error = await response.json()
          message = error.message || error.detail || message
        } catch {
          message = response.statusText || message
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

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

export const apiClient = new ApiClient()

/**
 * Lecture API
 */
export const lectureApi = {
  /**
   * Get all lectures
   */
  async list(): Promise<Lecture[]> {
    return apiClient.get<Lecture[]>('/api/v4/lectures')
  },

  /**
   * Get lecture by ID
   */
  async get(id: string): Promise<Lecture> {
    return apiClient.get<Lecture>(`/api/v4/lectures/${id}`)
  },

  /**
   * Ask a question about a lecture
   */
  async ask(lectureId: string, request: QaRequest): Promise<QaAnswer> {
    return apiClient.post<QaAnswer>(`/api/v4/lectures/${lectureId}/qa/ask`, request)
  },

  /**
   * Follow up with context
   */
  async followup(
    lectureId: string,
    answerId: string,
    question: string
  ): Promise<QaAnswer> {
    return apiClient.post<QaAnswer>(`/api/v4/lectures/${lectureId}/qa/followup`, {
      answerId,
      question,
    })
  },
}

/**
 * Settings API
 */
export interface UserSettings {
  theme?: 'light' | 'dark' | 'high-contrast'
  language?: 'ja' | 'en'
  fontSize?: 'small' | 'normal' | 'large'
  reducedMotion?: boolean
}

export const settingsApi = {
  /**
   * Get user preferences
   */
  async get(): Promise<UserSettings> {
    return apiClient.get<UserSettings>('/api/v4/settings/me')
  },

  /**
   * Update user preferences
   */
  async update(settings: UserSettings): Promise<UserSettings> {
    return apiClient.put<UserSettings>('/api/v4/settings/me', settings)
  },
}

/**
 * Health Check API
 */
export const healthApi = {
  /**
   * Check API health
   */
  async check(): Promise<{ status: string }> {
    return apiClient.get<{ status: string }>('/api/v4/health')
  },
}
