import type {
  LectureSummaryLatestResponse,
  SummaryKeyTerm,
  UserSettings,
} from '@/lib/api/client'
import type { AssistTermPayload } from '@/lib/stream'

export function mapSummaryKeyTermsToAssistTerms(
  keyTerms: readonly SummaryKeyTerm[]
): AssistTermPayload[] {
  return keyTerms.slice(0, 4).map((term) => ({
    term: term.term,
    explanation: term.explanation || '',
    translation: term.translation || term.term,
  }))
}

export function mapSummaryToAssistPoints(summary: string): string[] {
  return summary
    .split('。')
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3)
}

export function mapSummaryResponseToAssist(
  response: LectureSummaryLatestResponse
): { points: string[]; terms: AssistTermPayload[] } {
  return {
    points: mapSummaryToAssistPoints(response.summary),
    terms: mapSummaryKeyTermsToAssistTerms(response.key_terms),
  }
}

export function mergeAssistSettingsForUpdate(
  currentSettings: UserSettings | undefined,
  updates: Pick<UserSettings, 'assistSummaryEnabled' | 'assistKeytermsEnabled'>
): UserSettings {
  return {
    ...(currentSettings ?? {}),
    ...updates,
  }
}
