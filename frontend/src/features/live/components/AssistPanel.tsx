import { useState } from 'react'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useAudioInputStore } from '@/stores/audioInputStore'

const QUICK_QUESTIONS = ['この式の意味', 'もう一度説明して', 'この単語を日本語で']

export function AssistPanel({ onAskMiniQuestion }: { onAskMiniQuestion: (q: string) => void }) {
  const connection = useLiveSessionStore((state) => state.connection)
  const summaryPoints = useLiveSessionStore((state) => state.summaryPoints)
  const assistTerms = useLiveSessionStore((state) => state.assistTerms)
  const [miniQuestion, setMiniQuestion] = useState('')

  const isRecording = useAudioInputStore((state) => state.isRecording)
  const audioLevel = useAudioInputStore((state) => state.audioLevel)

  return (
    <div className="space-y-4">
      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">状態</h2>
        <StatusRow label="録音" value={isRecording ? 'ON' : 'OFF'} ok={isRecording} />
        <StatusRow label="文字起こし" value="稼働中" ok />
        <StatusRow label="翻訳" value="稼働中" ok />
        <StatusRow label="資料OCR" value="稼働中" ok />
        <StatusRow label="接続" value={connection} ok={connection === 'live'} />
        <div className="mt-2">
          <div className="text-xs text-fg-secondary mb-1">マイク入力レベル</div>
          <div className="h-2 rounded bg-bg-muted overflow-hidden">
            <div className="h-full bg-accent transition-all" style={{ width: `${Math.round(audioLevel * 100)}%` }} />
          </div>
        </div>
      </section>

      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">いまの要点</h2>
        {summaryPoints.length === 0 ? (
          <p className="text-sm text-fg-secondary">要点生成待機中</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {summaryPoints.map((point) => (
              <li key={point} className="bg-bg-muted rounded px-2 py-1">• {point}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">用語サポート</h2>
        {assistTerms.length === 0 ? (
          <p className="text-sm text-fg-secondary">用語抽出待機中</p>
        ) : (
          <ul className="space-y-2">
            {assistTerms.map((term) => (
              <li key={term.term} className="text-sm">
                <p className="font-medium text-fg-primary">{term.term} <span className="text-fg-secondary">({term.translation})</span></p>
                <p className="text-fg-secondary">{term.explanation}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card p-3 space-y-2">
        <h2 className="text-sm font-semibold">質問候補</h2>
        <div className="flex flex-wrap gap-2">
          {QUICK_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              className="badge badge-default cursor-pointer"
              onClick={() => onAskMiniQuestion(question)}
            >
              {question}
            </button>
          ))}
        </div>
        <div className="pt-2 border-t border-border">
          <label className="block text-xs text-fg-secondary mb-1" htmlFor="mini-qa-input">ミニ質問</label>
          <div className="flex gap-2">
            <input
              id="mini-qa-input"
              className="input"
              value={miniQuestion}
              onChange={(e) => setMiniQuestion(e.target.value)}
              placeholder="短い質問を入力"
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                const q = miniQuestion.trim()
                if (!q) return
                onAskMiniQuestion(q)
                setMiniQuestion('')
              }}
            >
              送信
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-fg-secondary">{label}</span>
      <span className={`inline-flex items-center gap-1 ${ok ? 'text-success' : 'text-warning'}`}>
        <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-success' : 'bg-warning'}`} />
        {value}
      </span>
    </div>
  )
}
