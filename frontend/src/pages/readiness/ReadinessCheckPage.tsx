import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { AppShell } from '@/components/common/AppShell'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'
import {
  demoApi,
  getApiErrorMessage,
  type ReadinessCheckRequest,
  type ReadinessCheckResponse,
} from '@/lib/api/client'

const INITIAL_FORM: ReadinessCheckRequest = {
  course_name: '',
  syllabus_text: '',
  first_material_blob_path: null,
  lang_mode: 'ja',
  jp_level_self: null,
  domain_level_self: null,
}

export function ReadinessCheckPage() {
  const { showToast } = useToast()
  const [form, setForm] = useState<ReadinessCheckRequest>(INITIAL_FORM)
  const [result, setResult] = useState<ReadinessCheckResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const updateNumberField = (
    key: 'jp_level_self' | 'domain_level_self',
    value: string
  ) => {
    const trimmed = value.trim()
    const parsed = Number(trimmed)
    setForm((current) => ({
      ...current,
      [key]: trimmed === '' || Number.isNaN(parsed) ? null : parsed,
    }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const courseName = form.course_name.trim()
    const syllabusText = form.syllabus_text.trim()

    if (!courseName || !syllabusText) {
      setErrorMessage('科目名とシラバス本文は必須です。')
      return
    }

    setIsSubmitting(true)
    setErrorMessage(null)

    try {
      const response = await demoApi.checkReadiness({
        ...form,
        course_name: courseName,
        syllabus_text: syllabusText,
        first_material_blob_path: form.first_material_blob_path?.trim() || null,
      })
      setResult(response)
      showToast({
        variant: 'success',
        title: 'Readiness Check を完了しました',
      })
    } catch (error) {
      const message = getApiErrorMessage(
        error,
        'Readiness Check APIの呼び出しに失敗しました。'
      )
      setErrorMessage(message)
      showToast({
        variant: 'danger',
        title: 'Readiness Check に失敗しました',
        message,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AppShell
      topbar={
        <div className="py-3 flex items-center justify-between gap-3">
          <h1 className="text-lg font-semibold">履修前サポート (F0)</h1>
          <div className="flex gap-2">
            <Link to="/lectures" className="btn btn-secondary">
              講義一覧
            </Link>
            <Link to="/" className="btn btn-secondary">
              ホーム
            </Link>
          </div>
        </div>
      }
    >
      <div className="max-w-5xl mx-auto grid gap-6 lg:grid-cols-2">
        <form className="card p-5 space-y-4" onSubmit={handleSubmit}>
          <h2 className="text-lg font-semibold">入力</h2>

          <div>
            <label htmlFor="course-name" className="block text-sm font-medium text-fg-primary mb-2">
              科目名 <span className="text-danger">*</span>
            </label>
            <input
              id="course-name"
              className="input"
              value={form.course_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, course_name: event.target.value }))
              }
              placeholder="例: 情報工学入門"
              required
            />
          </div>

          <div>
            <label htmlFor="syllabus-text" className="block text-sm font-medium text-fg-primary mb-2">
              シラバス本文 <span className="text-danger">*</span>
            </label>
            <textarea
              id="syllabus-text"
              className="input min-h-40"
              value={form.syllabus_text}
              onChange={(event) =>
                setForm((current) => ({ ...current, syllabus_text: event.target.value }))
              }
              placeholder="授業内容・評価方法・到達目標などを貼り付けてください"
              required
            />
          </div>

          <div>
            <label htmlFor="material-path" className="block text-sm font-medium text-fg-primary mb-2">
              初回資料Blobパス（任意）
            </label>
            <input
              id="material-path"
              className="input"
              value={form.first_material_blob_path ?? ''}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  first_material_blob_path: event.target.value,
                }))
              }
              placeholder="container/path/to/file.pdf"
            />
          </div>

          <div className="grid sm:grid-cols-3 gap-3">
            <div>
              <label htmlFor="lang-mode" className="block text-sm font-medium text-fg-primary mb-2">
                言語モード
              </label>
              <select
                id="lang-mode"
                className="input"
                value={form.lang_mode ?? 'ja'}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    lang_mode: event.target.value as ReadinessCheckRequest['lang_mode'],
                  }))
                }
              >
                <option value="ja">ja</option>
                <option value="easy-ja">easy-ja</option>
                <option value="en">en</option>
              </select>
            </div>

            <div>
              <label htmlFor="jp-level" className="block text-sm font-medium text-fg-primary mb-2">
                日本語自己評価 (1-5)
              </label>
              <input
                id="jp-level"
                className="input"
                type="number"
                min={1}
                max={5}
                value={form.jp_level_self ?? ''}
                onChange={(event) => updateNumberField('jp_level_self', event.target.value)}
              />
            </div>

            <div>
              <label htmlFor="domain-level" className="block text-sm font-medium text-fg-primary mb-2">
                専門知識自己評価 (1-5)
              </label>
              <input
                id="domain-level"
                className="input"
                type="number"
                min={1}
                max={5}
                value={form.domain_level_self ?? ''}
                onChange={(event) => updateNumberField('domain_level_self', event.target.value)}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? '判定中...' : 'Readiness Check 実行'}
          </button>

          {errorMessage && (
            <p className="text-sm text-danger" role="alert">
              {errorMessage}
            </p>
          )}
        </form>

        <section className="card p-5 space-y-4">
          <h2 className="text-lg font-semibold">結果</h2>

          {!result ? (
            <EmptyState
              variant="no-data"
              title="まだ結果がありません"
              description="左側の入力フォームから Readiness Check を実行してください。"
            />
          ) : (
            <div className="space-y-4">
              <div className="p-3 rounded-md bg-bg-muted border border-border">
                <p className="text-sm text-fg-secondary">Readiness Score</p>
                <p className="text-3xl font-bold text-fg-primary">{result.readiness_score}</p>
              </div>

              <div>
                <h3 className="font-semibold mb-2">重要語句</h3>
                <ul className="space-y-2">
                  {result.terms.map((term, index) => (
                    <li key={`${term.term}-${index}`} className="text-sm">
                      <span className="font-semibold">{term.term}</span>
                      <span className="text-fg-secondary">: {term.explanation}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="font-semibold mb-2">つまずきポイント</h3>
                <ul className="list-disc pl-5 space-y-1 text-sm">
                  {result.difficult_points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="font-semibold mb-2">推奨設定</h3>
                <ul className="list-disc pl-5 space-y-1 text-sm">
                  {result.recommended_settings.map((setting) => (
                    <li key={setting}>{setting}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="font-semibold mb-2">予習タスク</h3>
                <ul className="list-disc pl-5 space-y-1 text-sm">
                  {result.prep_tasks.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ul>
              </div>

              <p className="text-xs text-fg-secondary border-t border-border pt-3">
                {result.disclaimer}
              </p>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  )
}
