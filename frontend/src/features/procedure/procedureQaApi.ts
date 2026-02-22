import {
  procedureQaApi,
  type ProcedureQaLangMode,
} from '@/lib/api/client'

export function resolveProcedureQaLangMode(
  language: 'ja' | 'en' | undefined
): ProcedureQaLangMode {
  return language === 'en' ? 'en' : 'ja'
}

export async function requestProcedureQaAnswer(params: {
  query: string
  language: 'ja' | 'en' | undefined
}) {
  const { query, language } = params
  return procedureQaApi.ask({
    query,
    lang_mode: resolveProcedureQaLangMode(language),
  })
}
