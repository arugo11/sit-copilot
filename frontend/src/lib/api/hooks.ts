/**
 * TanStack Query Hooks
 * React Query hooks for API consumption with proper error handling and caching
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  settingsApi,
  type UserSettings,
  ApiError,
  getApiErrorMessage,
} from './client'
import { useToast } from '@/components/common/Toast'

// Query keys for cache management
export const queryKeys = {
  settings: {
    all: ['settings'] as const,
    me: ['settings', 'me'] as const,
  },
} as const

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
        message: getApiErrorMessage(error, 'Updating settings failed.'),
      })
    }
  })
}
