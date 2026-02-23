import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { AppShell } from '@/components/common/AppShell'
import { useToast } from '@/components/common/Toast'
import { QAStreamBlocks } from '@/features/review/components/QAStreamBlocks'
import {
  mapProcedureQaResponseToChunk,
  mapProcedureQaResponseToDone,
} from '@/features/procedure/procedureQaMapper'
import { requestProcedureQaAnswer } from '@/features/procedure/procedureQaApi'
import { createReviewAnswerId } from '@/features/review/reviewQaApi'
import { useQaAnnouncer } from '@/hooks/useLiveRegion'
import { ApiError, getApiErrorMessage } from '@/lib/api/client'
import { useUserSettings } from '@/lib/api/hooks'
import { useReviewQaStore } from '@/stores/reviewQaStore'

export function ProcedurePage() {
  const { showToast } = useToast()
  const { announceQaStatus } = useQaAnnouncer()
  const { data: userSettings } = useUserSettings()

  const [question, setQuestion] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const qaTurns = useReviewQaStore((state) => state.qaTurns)
  const qaStatus = useReviewQaStore((state) => state.status)
  const submitQuestion = useReviewQaStore((state) => state.submitQuestion)
  const applyChunk = useReviewQaStore((state) => state.applyChunk)
  const applyDone = useReviewQaStore((state) => state.applyDone)
  const failAnswer = useReviewQaStore((state) => state.failAnswer)
  const retryAnswer = useReviewQaStore((state) => state.retryAnswer)
  const reset = useReviewQaStore((state) => state.reset)

  useEffect(() => {
    reset()
    return () => {
      reset()
    }
  }, [reset])

  const executeQuestion = useCallback(
    async (
      rawQuestion: string,
      options: {
        existingAnswerId?: string
      } = {}
    ) => {
      const normalizedQuestion = rawQuestion.trim()
      if (!normalizedQuestion || isSubmitting) {
        return
      }

      const answerId = options.existingAnswerId ?? createReviewAnswerId()
      setIsSubmitting(true)

      if (options.existingAnswerId) {
        retryAnswer(answerId)
      } else {
        submitQuestion(normalizedQuestion, answerId)
      }
      announceQaStatus('generating', userSettings?.language === 'en' ? 'en' : 'ja')

      try {
        const response = await requestProcedureQaAnswer({
          query: normalizedQuestion,
          language: userSettings?.language,
        })

        applyChunk(mapProcedureQaResponseToChunk(answerId, response))
        applyDone(mapProcedureQaResponseToDone(answerId, response))
        announceQaStatus('done', userSettings?.language === 'en' ? 'en' : 'ja')

        if (response.fallback.trim()) {
          showToast({
            variant: 'warning',
            title: '根拠が不足している回答です',
            message: response.action_next,
          })
        }
      } catch (error) {
        failAnswer(answerId)
        announceQaStatus('error', userSettings?.language === 'en' ? 'en' : 'ja')

        if (error instanceof ApiError && error.status === 401) {
          showToast({
            variant: 'danger',
            title: '認証エラー',
            message: 'トークン設定を確認してください (X-Procedure-Token)。',
          })
          return
        }

        showToast({
          variant: 'danger',
          title: '回答の取得に失敗しました',
          message: getApiErrorMessage(
            error,
            '手続きQAの回答生成中にエラーが発生しました。'
          ),
        })
      } finally {
        setIsSubmitting(false)
      }
    },
    [
      announceQaStatus,
      applyChunk,
      applyDone,
      failAnswer,
      isSubmitting,
      retryAnswer,
      showToast,
      submitQuestion,
      userSettings?.language,
    ]
  )

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isSubmitting) {
      return
    }
    setQuestion('')
    void executeQuestion(trimmed)
  }

  const handleRetry = useCallback(
    (answerId: string) => {
      if (isSubmitting) {
        return
      }
      const targetTurn = qaTurns.find((turn) => turn.answerId === answerId)
      if (!targetTurn) {
        return
      }
      void executeQuestion(targetTurn.question, { existingAnswerId: answerId })
    },
    [executeQuestion, isSubmitting, qaTurns]
  )

  const handleRegenerate = useCallback(
    (retryQuestion: string) => {
      if (isSubmitting) {
        return
      }
      void executeQuestion(retryQuestion)
    },
    [executeQuestion, isSubmitting]
  )

  const handleCitationSelect = useCallback(
    (citationId: string) => {
      showToast({
        variant: 'info',
        title: '参照ソース',
        message: `ソースID: ${citationId}`,
      })
    },
    [showToast]
  )

  return (
    <AppShell
      topbar={
        <div className="py-3 flex items-center justify-between gap-3">
          <h1 className="text-lg font-semibold">手続きサポートQA</h1>
          <div className="flex gap-2">
            <Link to="/lectures" className="btn btn-secondary">
              講義一覧
            </Link>
            <Link to="/settings" className="btn btn-secondary">
              設定
            </Link>
            <Link to="/" className="btn btn-secondary">
              ホーム
            </Link>
          </div>
        </div>
      }
    >
      <div className="max-w-4xl mx-auto space-y-4">
        <form className="card p-4 space-y-3" onSubmit={handleSubmit}>
          <h2 className="font-semibold">手続きに関する質問を入力してください</h2>
          <textarea
            className="input min-h-24"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="例: 在留カード更新のときに必要な提出書類は？"
          />
          <div className="flex gap-2 items-center">
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? '送信中...' : '送信'}
            </button>
            <span
              className={`badge ${
                qaStatus === 'streaming'
                  ? 'badge-warning'
                  : qaStatus === 'error'
                    ? 'badge-danger'
                    : 'badge-success'
              }`}
            >
              {qaStatus}
            </span>
          </div>
        </form>

        <QAStreamBlocks
          turns={qaTurns}
          isBusy={isSubmitting}
          labels={{
            resume: '再試行',
            regenerate: '再生成',
          }}
          onCitationSelect={handleCitationSelect}
          onRetry={handleRetry}
          onRegenerate={handleRegenerate}
        />
      </div>
    </AppShell>
  )
}
