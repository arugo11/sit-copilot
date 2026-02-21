/**
 * Lecture Live Page
 * Based on docs/frontend.md Section 8.3
 */

import { prefersReducedMotion } from '@/lib/utils'

function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}

export function LectureLivePage() {

  return (
    <div className="h-screen flex flex-col">
      {/* Top Bar */}
      <header className="bg-bg-surface border-b border-border px-4 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold truncate">機械学習入門</h1>
            <span className={cn(
              'badge badge-danger',
              !prefersReducedMotion() && 'animate-pulse'
            )}>
              <span className="sr-only">講義進行中:</span>LIVE
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-fg-secondary">字幕 1.2s</span>
            <select className="input text-sm py-1">
              <option>日本語</option>
              <option>English</option>
            </select>
          </div>
        </div>
      </header>

      {/* Main Content - 3 Pane Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane - Source Panel */}
        <aside className="w-80 bg-bg-surface border-r border-border p-4 overflow-y-auto">
          <h2 className="font-semibold mb-4">資料</h2>
          <div className="card bg-bg-muted aspect-square flex items-center justify-center">
            <p className="text-fg-secondary text-sm">投影資料スナップショット</p>
          </div>
        </aside>

        {/* Center Pane - Transcript Panel */}
        <main className="flex-1 flex flex-col bg-bg-page">
          <div className="flex-1 p-4 overflow-y-auto">
            <div className="max-w-3xl mx-auto space-y-3">
              {/* Sample Transcript Lines */}
              {[
                { time: '10:00', speaker: '先生', text: '皆さん、機械学習について学びましょう', translation: 'Let\'s learn about machine learning' },
                { time: '10:05', speaker: '先生', text: '機械学習は、データから学習するAIの手法です', translation: 'Machine learning is an AI method that learns from data' },
                { time: '10:10', speaker: '先生', text: '大きく分けて、教師あり学習と教師なし学習があります', translation: 'There are mainly supervised learning and unsupervised learning' },
              ].map((line, i) => (
                <div key={i} className="card p-4 space-y-1">
                  <div className="flex items-center gap-2 text-xs text-fg-secondary">
                    <span>{line.time}</span>
                    <span>•</span>
                    <span>{line.speaker}</span>
                  </div>
                  <p className="text-fg-primary text-lg leading-relaxed">
                    {line.text}
                  </p>
                  <p className="text-fg-secondary text-base">
                    {line.translation}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Auto-scroll Toggle */}
          <div className="bg-bg-surface border-t border-border px-4 py-2">
            <button className="btn btn-primary btn-sm w-full" aria-label="字幕を現在の位置に戻す">
              現在位置に戻る
            </button>
          </div>
        </main>

        {/* Right Pane - Assist Panel */}
        <aside className="w-72 bg-bg-surface border-l border-border p-4 overflow-y-auto">
          <h2 className="font-semibold mb-4">補助</h2>

          {/* Status */}
          <div className="space-y-2 mb-6">
            <h3 className="text-sm font-medium">状態</h3>
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-success rounded-full" aria-hidden="true" />
                <svg className="w-4 h-4 text-success" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>録音中</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-success rounded-full" aria-hidden="true" />
                <svg className="w-4 h-4 text-success" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>文字起こし中</span>
              </div>
            </div>
          </div>

          {/* Key Points */}
          <div className="space-y-2 mb-6">
            <h3 className="text-sm font-medium">要点</h3>
            <ul className="space-y-2 text-sm text-fg-secondary">
              <li className="p-2 bg-bg-muted rounded">• 機械学習はデータから学習する</li>
              <li className="p-2 bg-bg-muted rounded">• 教師あり/なしがある</li>
            </ul>
          </div>

          {/* QA Input */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">質問</h3>
            <input
              type="text"
              className="input"
              placeholder="質問を入力..."
            />
          </div>
        </aside>
      </div>
    </div>
  )
}
