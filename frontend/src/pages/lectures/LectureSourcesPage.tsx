/**
 * Lecture Sources Page
 */

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from '@/components/common/EmptyState'

type SourceType = 'audio' | 'slide' | 'board' | 'ocr'

interface SourceRow {
  id: string
  time: string
  type: SourceType
  text: string
  confidence?: number
}

function buildMockRows(locale: 'ja' | 'en'): SourceRow[] {
  if (locale === 'en') {
    return [
      { id: '1', time: '10:00', type: 'audio', text: 'Lecture audio sample 1', confidence: 0.96 },
      { id: '2', time: '10:03', type: 'slide', text: 'Slide OCR sample', confidence: 0.9 },
      { id: '3', time: '10:05', type: 'audio', text: 'Lecture audio sample 2', confidence: 0.94 },
      { id: '4', time: '10:07', type: 'ocr', text: 'OCR sample text', confidence: 0.82 },
      { id: '5', time: '10:08', type: 'board', text: 'Whiteboard sample text', confidence: 0.79 },
    ]
  }

  return [
    { id: '1', time: '10:00', type: 'audio', text: 'これは講義音声サンプル1です', confidence: 0.96 },
    { id: '2', time: '10:03', type: 'slide', text: 'これはスライドサンプルです', confidence: 0.9 },
    { id: '3', time: '10:05', type: 'audio', text: 'これは講義音声サンプル2です', confidence: 0.94 },
    { id: '4', time: '10:07', type: 'ocr', text: 'これはOCRサンプルです', confidence: 0.82 },
    { id: '5', time: '10:08', type: 'board', text: 'これは板書サンプルです', confidence: 0.79 },
  ]
}

export function LectureSourcesPage() {
  const { t, i18n } = useTranslation()
  const locale: 'ja' | 'en' =
    (i18n.resolvedLanguage ?? i18n.language).startsWith('en') ? 'en' : 'ja'

  const rows = useMemo(() => buildMockRows(locale), [locale])
  const [selectedRow, setSelectedRow] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<'all' | SourceType>('all')
  const [keyword, setKeyword] = useState('')

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (typeFilter !== 'all' && row.type !== typeFilter) {
        return false
      }
      if (keyword && !row.text.toLowerCase().includes(keyword.toLowerCase())) {
        return false
      }
      return true
    })
  }, [keyword, rows, typeFilter])

  const typeLabel = (type: SourceType): string =>
    t(`lectureSources.types.${type}`)

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg-primary">{t('lectureSources.title')}</h1>
        <p className="text-fg-secondary">{t('lectureSources.description')}</p>
      </div>

      <div className="flex flex-wrap gap-4 mb-6">
        <select
          className="input max-w-56"
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value as 'all' | SourceType)}
        >
          <option value="all">{t('lectureSources.filters.all')}</option>
          <option value="audio">{t('lectureSources.filters.audio')}</option>
          <option value="slide">{t('lectureSources.filters.slide')}</option>
          <option value="board">{t('lectureSources.filters.board')}</option>
          <option value="ocr">OCR</option>
        </select>
        <input
          type="text"
          className="input flex-1"
          placeholder={t('lectureSources.filters.keywordPlaceholder')}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
        />
      </div>

      {filteredRows.length === 0 ? (
        <EmptyState
          variant="no-results"
          title={t('lectureSources.empty.title')}
          description={t('lectureSources.empty.description')}
          action={
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setTypeFilter('all')
                setKeyword('')
              }}
            >
              {t('lectureSources.empty.clear')}
            </button>
          }
        />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full" role="table">
            <caption className="sr-only">{t('lectureSources.table.caption')}</caption>
            <thead className="bg-bg-muted">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">{t('lectureSources.table.time')}</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">{t('lectureSources.table.type')}</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">{t('lectureSources.table.excerpt')}</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">{t('lectureSources.table.confidence')}</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">{t('lectureSources.table.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredRows.map((source) => (
                <tr
                  key={source.id}
                  className={selectedRow === source.id ? 'bg-bg-muted/50' : 'hover:bg-bg-muted/50'}
                  tabIndex={0}
                  role="row"
                  aria-selected={selectedRow === source.id}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      setSelectedRow(source.id)
                    }
                  }}
                  onClick={() => setSelectedRow(source.id)}
                >
                  <td className="px-4 py-3 text-sm">{source.time}</td>
                  <td className="px-4 py-3 text-sm"><span className="badge badge-default">{typeLabel(source.type)}</span></td>
                  <td className="px-4 py-3 text-sm text-fg-secondary max-w-md truncate">{source.text}</td>
                  <td className="px-4 py-3 text-sm text-fg-secondary">{source.confidence ? `${Math.round(source.confidence * 100)}%` : '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={(event) => {
                        event.stopPropagation()
                        setSelectedRow(source.id)
                      }}
                    >
                      {t('lectureSources.table.open')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
