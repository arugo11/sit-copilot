/**
 * Landing Page
 * Based on docs/frontend.md Section 8.1
 */

import { Link } from 'react-router-dom'

export function LandingPage() {
  return (
    <div className="min-h-screen bg-bg-page">
      <div className="container mx-auto px-4 py-12">
        <div className="grid lg:grid-cols-5 gap-12 items-center">
          {/* Left Content (60%) */}
          <div className="lg:col-span-3 space-y-6">
            <h1 className="text-4xl md:text-5xl font-bold text-fg-primary">
              講義支援アプリ
            </h1>
            <p className="text-lg text-fg-secondary">
              ログイン不要で、講義中のリアルタイム字幕と翻訳をすぐに利用できます。
            </p>

            {/* Target Audience */}
            <div className="flex flex-wrap gap-4 py-4">
              <div className="badge badge-default">留学生</div>
              <div className="badge badge-default">障がいのある学生</div>
              <div className="badge badge-default">日本語学生</div>
            </div>

            {/* Key Features */}
            <div className="space-y-3">
              <h2 className="text-xl font-semibold text-fg-primary">主な機能</h2>
              <ul className="space-y-2 text-fg-secondary" role="list">
                <li className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-success mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>リアルタイム字幕と翻訳</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Right Content (40%) */}
          <div className="lg:col-span-2 space-y-6">
            <div className="card p-6 space-y-4">
              <h2 className="text-xl font-semibold text-fg-primary text-center">
                講義を始める
              </h2>

              {/* Lecture Start Button */}
              <Link to="/lectures" className="btn btn-primary w-full text-center block">
                講義一覧を開く
              </Link>

              {/* Language Selector */}
              <div className="pt-4 border-t border-border">
                <label htmlFor="language" className="block text-sm font-medium text-fg-primary mb-2">
                  言語 / Language
                </label>
                <select
                  id="language"
                  className="input"
                  defaultValue="ja"
                >
                  <option value="ja">日本語</option>
                  <option value="en">English</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
