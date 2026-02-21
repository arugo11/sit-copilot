/**
 * TanStack Query Hooks
 * React Query hooks for API consumption with proper error handling and caching
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  lectureApi,
  settingsApi,
  type Lecture,
  type QaRequest,
  type QaAnswer,
  type UserSettings,
  ApiError,
} from './client'
import { useToast } from '@/components/common/Toast'

// Query keys for cache management
export const queryKeys = {
  lectures: {
    all: ['lectures'] as const,
    lists: () => ['lectures', 'list'] as const,
    details: () => ['lectures', 'detail'] as const,
    detail: (id: string) => ['lectures', 'detail', id] as const,
  },
  qa: {
    all: ['qa'] as const,
    answers: (lectureId: string) => ['qa', 'lectures', lectureId] as const,
    answer: (lectureId: string, answerId: string) => ['qa', 'lectures', lectureId, answerId] as const,
  },
  settings: {
    all: ['settings'] as const,
    me: ['settings', 'me'] as const,
  },
} as const

// Shared error handler
function handleApiError(error: unknown, context: string): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return `${context} failed`
}

/**
 * Lecture Query Hooks
 */

export interface LecturesFilters {
  status?: 'upcoming' | 'live' | 'ended'
}

/**
 * Fetch all lectures with optional filters
 * @param filters - Optional status filter
 */
export function useLectures(filters?: LecturesFilters) {
  return useQuery<Lecture[], ApiError>({
    queryKey: filters?.status
      ? [...queryKeys.lectures.lists(), { status: filters.status }]
      : queryKeys.lectures.lists(),
    queryFn: async () => {
      const lectures = await lectureApi.list()
      if (filters?.status) {
        return lectures.filter((l) => l.status === filters.status)
      }
      return lectures
    }
  })
}

/**
 * Fetch a single lecture by ID
 * @param id - Lecture ID
 */
export function useLecture(id: string) {
  return useQuery<Lecture, ApiError>({
    queryKey: queryKeys.lectures.detail(id),
    queryFn: () => lectureApi.get(id),
    enabled: !!id,
  })
}

/**
 * QA Mutation Hooks
 */

export interface AskQuestionVariables {
  lectureId: string
  request: QaRequest
}

/**
 * Ask a question about a lecture
 * Invalidates lecture queries on success
 */
export function useAskQuestion() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  return useMutation<QaAnswer, ApiError, AskQuestionVariables>({
    mutationFn: ({ lectureId, request }: AskQuestionVariables) => lectureApi.ask(lectureId, request),
    onSuccess: (_data, variables) => {
      // Invalidate lecture queries to refresh any related data
      queryClient.invalidateQueries({ queryKey: queryKeys.lectures.detail(variables.lectureId) })
    },
    onError: (error) => {
      showToast({
        variant: 'danger',
        title: 'Failed to ask question',
        message: handleApiError(error, 'Asking question'),
      })
    }
  })
}

export interface FollowupVariables {
  lectureId: string
  answerId: string
  question: string
}

/**
 * Ask a follow-up question with context from previous answer
 * Invalidates QA queries on success
 */
export function useFollowup() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  return useMutation<QaAnswer, ApiError, FollowupVariables>({
    mutationFn: ({ lectureId, answerId, question }: FollowupVariables) =>
      lectureApi.followup(lectureId, answerId, question),
    onSuccess: (_data, variables) => {
      // Invalidate QA queries for this lecture
      queryClient.invalidateQueries({ queryKey: queryKeys.qa.answers(variables.lectureId) })
    },
    onError: (error) => {
      showToast({
        variant: 'danger',
        title: 'Failed to follow up',
        message: handleApiError(error, 'Follow-up question'),
      })
    }
  })
}

/**
 * Settings Query Hooks
 */

/**
 * Fetch user settings
 */
export function useUserSettings() {
  return useQuery<UserSettings, ApiError>({
    queryKey: queryKeys.settings.me,
    queryFn: () => settingsApi.get(),
  })
}

/**
 * Settings Mutation Hooks
 */

export interface UpdateSettingsVariables {
  settings: UserSettings
}

/**
 * Update user settings
 * Invalidates settings queries on success
 */
export function useUpdateSettings() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  return useMutation<UserSettings, ApiError, UpdateSettingsVariables>({
    mutationFn: ({ settings }: UpdateSettingsVariables) => settingsApi.update(settings),
    onSuccess: () => {
      // Invalidate settings queries to refresh data
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.me })
    },
    onError: (error) => {
      showToast({
        variant: 'danger',
        title: 'Failed to update settings',
        message: handleApiError(error, 'Updating settings'),
      })
    }
  })
}
