/**
 * Lecture Sources Page
 */

import { useMemo, useState } from 'react'
import { EmptyState } from '@/components/common/EmptyState'

interface SourceRow {
  id: string
  time: string
  type: 'audio' | 'slide' | 'board' | 'ocr'
  text: string
  confidence?: number
}

const MOCK_ROWS: SourceRow[] = [
  { id: '1', time: '10:00', type: 'audio', text: 'これはデモ文です（音声サンプル1）', confidence: 0.96 },
  { id: '2', time: '10:03', type: 'slide', text: 'これはデモ文です（スライドサンプル）', confidence: 0.9 },
  { id: '3', time: '10:05', type: 'audio', text: 'これはデモ文です（音声サンプル2）', confidence: 0.94 },
  { id: '4', time: '10:07', type: 'ocr', text: 'これはデモ文です（OCRサンプル）', confidence: 0.82 },
  { id: '5', time: '10:08', type: 'board', text: 'これはデモ文です（板書サンプル）', confidence: 0.79 },
]

export function LectureSourcesPage() {
  const [selectedRow, setSelectedRow] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<'all' | SourceRow['type']>('all')
  const [keyword, setKeyword] = useState('')

  const filteredRows = useMemo(() => {
    return MOCK_ROWS.filter((row) => {
      if (typeFilter !== 'all' && row.type !== typeFilter) {
        return false
      }
      if (keyword && !row.text.toLowerCase().includes(keyword.toLowerCase())) {
        return false
      }
      return true
    })
  }, [keyword, typeFilter])

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg-primary">ソース一覧</h1>
        <p className="text-fg-secondary">OCRと文字起こしの元データ</p>
      </div>

      <div className="flex flex-wrap gap-4 mb-6">
        <select className="input max-w-56" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as 'all' | SourceRow['type'])}>
          <option value="all">すべての種別</option>
          <option value="audio">音声</option>
          <option value="slide">投影資料</option>
          <option value="board">板書</option>
          <option value="ocr">OCR</option>
        </select>
        <input type="text" className="input flex-1" placeholder="キーワードで検索..." value={keyword} onChange={(e) => setKeyword(e.target.value)} />
      </div>

      {filteredRows.length === 0 ? (
        <EmptyState
          variant="no-results"
          title="該当するソースがありません"
          description="フィルタまたはキーワードを変更してください。"
          action={<button type="button" className="btn btn-secondary" onClick={() => { setTypeFilter('all'); setKeyword('') }}>フィルタを解除</button>}
        />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full" role="table">
            <caption className="sr-only">講義ソース一覧</caption>
            <thead className="bg-bg-muted">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">時刻</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">種別</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">抜粋</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">信頼度</th>
                <th className="px-4 py-2 text-left text-sm font-medium" scope="col">操作</th>
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
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedRow(source.id)
                    }
                  }}
                  onClick={() => setSelectedRow(source.id)}
                >
                  <td className="px-4 py-3 text-sm">{source.time}</td>
                  <td className="px-4 py-3 text-sm"><span className="badge badge-default">{source.type}</span></td>
                  <td className="px-4 py-3 text-sm text-fg-secondary max-w-md truncate">{source.text}</td>
                  <td className="px-4 py-3 text-sm text-fg-secondary">{source.confidence ? `${Math.round(source.confidence * 100)}%` : '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); setSelectedRow(source.id) }}>
                      開く
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
