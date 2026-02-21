/**
 * Lecture Review Page
 * Based on docs/frontend.md Section 8.4
 */

import { useState } from 'react'

export function LectureReviewPage() {
  const [selectedTopic, setSelectedTopic] = useState<number | null>(null)

  return (
    <div className="h-screen flex flex-col">
      {/* Top Bar */}
      <header className="bg-bg-surface border-b border-border px-4 py-2">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">機械学習入門 - レビュー</h1>
          <a href="/" className="btn btn-secondary btn-sm">
            講義一覧に戻る
          </a>
        </div>
      </header>

      {/* Main Content - 3 Pane Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane - Session Overview */}
        <aside className="w-72 bg-bg-surface border-r border-border p-4 overflow-y-auto">
          <h2 className="font-semibold mb-4">講義情報</h2>
          <div className="space-y-3 text-sm">
            <div>
              <span className="text-fg-secondary">講師:</span>
              <p className="font-medium">田中 太郎</p>
            </div>
            <div>
              <span className="text-fg-secondary">日時:</span>
              <p className="font-medium">2025/01/15 10:00-11:30</p>
            </div>
          </div>

          {/* Summary */}
          <div className="mt-6">
            <h3 className="font-semibold mb-2">要約</h3>
            <p className="text-sm text-fg-secondary">
              機械学習の基本概念について学びました。教師あり学習と教師なし学習の違い、
              代表的なアルゴリズムについて説明しました。
            </p>
          </div>

          {/* Topics */}
          <div className="mt-6">
            <h3 className="font-semibold mb-2">トピック</h3>
            <ul className="space-y-1 text-sm" role="listbox" aria-label="講義トピック">
              {['機械学習の定義', '教師あり学習', '教師なし学習'].map((topic, i) => (
                <li
                  key={i}
                  role="option"
                  aria-selected={selectedTopic === i}
                  tabIndex={0}
                  className={selectedTopic === i
                    ? 'p-2 bg-accent/20 rounded cursor-pointer hover:bg-accent/30 border-l-2 border-accent'
                    : 'p-2 bg-bg-muted rounded cursor-pointer hover:bg-bg-muted/80'
                  }
                  onClick={() => setSelectedTopic(i)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedTopic(i)
                    }
                  }}
                >
                  {topic}
                </li>
              ))}
            </ul>
          </div>
        </aside>

        {/* Center Pane - QA Thread */}
        <main className="flex-1 flex flex-col bg-bg-page">
          <div className="flex-1 p-4 overflow-y-auto">
            <div className="max-w-2xl mx-auto space-y-4">
              {/* QA Input */}
              <div className="card p-4 space-y-3">
                <h2 className="font-semibold">質問する</h2>
                <label htmlFor="qa-input" className="sr-only">質問を入力</label>
                <textarea
                  id="qa-input"
                  className="input min-h-24"
                  placeholder="講義について質問を入力してください..."
                />
                <div className="flex gap-2">
                  <select className="input flex-1">
                    <option>全体</option>
                    <option>現在のトピック</option>
                  </select>
                  <button className="btn btn-primary">送信</button>
                </div>
              </div>

              {/* Sample QA */}
              <div className="card p-4 space-y-3">
                <div className="flex items-start gap-2 text-sm text-fg-secondary">
                  <span>Q:</span>
                  <p>機械学習とは何ですか？</p>
                </div>
                <div className="pl-4 space-y-2">
                  <p className="text-fg-primary">
                    機械学習は、データからパターンを学習し、予測や判断を行うAIの手法です。
                  </p>
                  {/* Citation Chips */}
                  <div className="flex flex-wrap gap-2" role="group" aria-label="引用元">
                    <button
                      type="button"
                      className="badge badge-default text-xs cursor-pointer hover:bg-bg-muted"
                      aria-pressed="false"
                    >
                      発言 10:05
                    </button>
                    <button
                      type="button"
                      className="badge badge-default text-xs cursor-pointer hover:bg-bg-muted"
                      aria-pressed="false"
                    >
                      資料 p.3
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Right Pane - Source Viewer */}
        <aside className="w-80 bg-bg-surface border-l border-border p-4 overflow-y-auto">
          <h2 className="font-semibold mb-4">ソースビューア</h2>

          {/* Transcript Segment */}
          <div className="space-y-3">
            <div className="card p-3 space-y-2">
              <div className="flex items-center gap-2 text-xs text-fg-secondary">
                <span>10:05</span>
                <span>先生</span>
              </div>
              <p className="text-sm text-fg-primary">
                機械学習は、データから学習するAIの手法です。
                大きく分けて、教師あり学習と教師なし学習があります。
              </p>
              <div className="card bg-bg-muted aspect-square flex items-center justify-center">
                <p className="text-fg-secondary text-xs">資料スナップショット</p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
