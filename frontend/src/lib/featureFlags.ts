type LangMode = 'ja' | 'easy-ja' | 'en'

function readBooleanEnv(value: string | boolean | undefined, fallback: boolean): boolean {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value !== 'string') {
    return fallback
  }
  const normalized = value.trim().toLowerCase()
  if (normalized === 'true' || normalized === '1' || normalized === 'yes' || normalized === 'on') {
    return true
  }
  if (normalized === 'false' || normalized === '0' || normalized === 'no' || normalized === 'off') {
    return false
  }
  return fallback
}

function readIntegerEnv(value: string | undefined, fallback: number): number {
  if (typeof value !== 'string') {
    return fallback
  }
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export const LIVE_FEATURE_FLAGS = {
  translation: readBooleanEnv(
    import.meta.env.VITE_LECTURE_LIVE_TRANSLATION_ENABLED,
    false
  ),
  summary: readBooleanEnv(
    import.meta.env.VITE_LECTURE_LIVE_SUMMARY_ENABLED,
    false
  ),
  keyterms: readBooleanEnv(
    import.meta.env.VITE_LECTURE_LIVE_KEYTERMS_ENABLED,
    false
  ),
  qa: readBooleanEnv(
    import.meta.env.VITE_LECTURE_QA_ENABLED,
    false
  ),
  idleAutostopSeconds: readIntegerEnv(
    import.meta.env.VITE_LECTURE_IDLE_AUTOSTOP_SECONDS,
    120
  ),
} as const

export function getSelectableLanguageModes(): LangMode[] {
  return LIVE_FEATURE_FLAGS.translation ? ['ja', 'easy-ja', 'en'] : ['ja']
}

export function sanitizeSelectableLanguage(mode: LangMode | undefined): LangMode {
  if (mode && getSelectableLanguageModes().includes(mode)) {
    return mode
  }
  return 'ja'
}
