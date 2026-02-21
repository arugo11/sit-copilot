/**
 * Lecture Sources Page
 * Based on docs/frontend.md Section 8.5
 */

import { useState } from 'react'

export function LectureSourcesPage() {
  const [selectedRow, setSelectedRow] = useState<number | null>(null)

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg-primary">ソース一覧</h1>
        <p className="text-fg-secondary">OCRと文字起こしの元データ</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <select className="input">
          <option>すべての種別</option>
          <option>音声</option>
          <option>投影資料</option>
          <option>板書</option>
          <option>OCR</option>
        </select>
        <input type="text" className="input flex-1" placeholder="キーワードで検索..." />
      </div>

      {/* Sources Table */}
      <div className="card overflow-hidden">
        <table className="w-full" role="table">
          <caption className="sr-only">講義ソース一覧</caption>
          <thead className="bg-bg-muted">
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium" scope="col">時刻</th>
              <th className="px-4 py-2 text-left text-sm font-medium" scope="col">種別</th>
              <th className="px-4 py-2 text-left text-sm font-medium" scope="col">抜粋</th>
              <th className="px-4 py-2 text-left text-sm font-medium" scope="col">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {[
              { time: '10:00', type: '音声', text: '機械学習について学びましょう' },
              { time: '10:05', type: '音声', text: '機械学習はデータから学習するAIの手法です' },
              { time: '10:03', type: '投影資料', text: '機械学習の定義と概要' },
              { time: '10:07', type: '板書OCR', text: '教師あり学習 教師なし学習' },
            ].map((source, i) => (
              <tr
                key={i}
                className={selectedRow === i ? 'bg-bg-muted/50' : 'hover:bg-bg-muted/50'}
                tabIndex={0}
                role="row"
                aria-selected={selectedRow === i}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedRow(i)
                  }
                }}
                onClick={() => setSelectedRow(i)}
              >
                <td className="px-4 py-3 text-sm" scope="row">{source.time}</td>
                <td className="px-4 py-3 text-sm">
                  <span className="badge badge-default">{source.type}</span>
                </td>
                <td className="px-4 py-3 text-sm text-fg-secondary max-w-md truncate">
                  {source.text}
                </td>
                <td className="px-4 py-3 text-sm">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      // Handle open action
                    }}
                  >
                    開く
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
