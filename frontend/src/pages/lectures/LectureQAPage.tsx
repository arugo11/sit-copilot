/**
 * Lecture QA Page
 * Simplified QA interface for lecture questions
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AppShell } from '@/components/common/AppShell'
import { useToast } from '@/components/common/Toast'
import { QAStreamBlocks } from '@/features/review/components/QAStreamBlocks'
import {
  mapLectureQaResponseToChunk,
  mapLectureQaResponseToDone,
} from '@/features/review/qaResponseMapper'
import {
  createReviewAnswerId,
  requestReviewQaAnswer,
  warmupReviewQaIndex,
} from '@/features/review/reviewQaApi'
import { useQaAnnouncer } from '@/hooks/useLiveRegion'
import { ApiError, getApiErrorMessage } from '@/lib/api/client'
import { useUserSettings } from '@/lib/api/hooks'
import { useReviewQaStore } from '@/stores/reviewQaStore'

export function LectureQAPage() {
  const navigate = useNavigate()
  const { id, session_id } = useParams<{ id?: string; session_id?: string }>()
  const sessionId = session_id ?? id ?? 'demo-session'

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

  const indexWarmupAttemptedRef = useRef(false)
  const successfulTurnCountRef = useRef(0)

  useEffect(() => {
    reset()
    indexWarmupAttemptedRef.current = false
    successfulTurnCountRef.current = 0
    return () => {
      reset()
    }
  }, [reset, sessionId])

  const warmupQaIndex = useCallback(() => {
    if (indexWarmupAttemptedRef.current) {
      return
    }
    indexWarmupAttemptedRef.current = true
    void warmupReviewQaIndex(sessionId).catch((error) => {
      showToast({
        variant: 'warning',
        title: 'QA索引の事前構築に失敗しました',
        message: getApiErrorMessage(
          error,
          '質問時に必要な索引を作成できませんでした。'
        ),
      })
    })
  }, [sessionId, showToast])

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
      announceQaStatus('generating', 'ja')
      warmupQaIndex()

      try {
        const response = await requestReviewQaAnswer({
          sessionId,
          question: normalizedQuestion,
          language: userSettings?.language,
          hasSuccessfulTurn: successfulTurnCountRef.current > 0,
        })

        applyChunk(mapLectureQaResponseToChunk(answerId, response))
        applyDone(mapLectureQaResponseToDone(answerId))
        successfulTurnCountRef.current += 1
        announceQaStatus('done', 'ja')

        if (response.fallback) {
          showToast({
            variant: 'warning',
            title: '根拠が不足している回答です',
            message: response.action_next,
          })
        }
      } catch (error) {
        failAnswer(answerId)
        announceQaStatus('error', 'ja')

        if (error instanceof ApiError && error.status === 401) {
          showToast({
            variant: 'danger',
            title: '認証エラー',
            message:
              'デモトークン設定を確認してください (X-Lecture-Token / X-User-Id)。',
          })
          return
        }
        if (error instanceof ApiError && error.status === 404) {
          showToast({
            variant: 'danger',
            title: 'セッションが見つかりません',
            message: '講義一覧へ戻ります。',
          })
          navigate('/lectures')
          return
        }
        if (error instanceof ApiError && error.status === 503) {
          showToast({
            variant: 'danger',
            title: 'QAバックエンド利用不可',
            message:
              '現在は回答生成サービスを利用できません。しばらくして再試行してください。',
          })
          return
        }

        showToast({
          variant: 'danger',
          title: '回答の取得に失敗しました',
          message: getApiErrorMessage(
            error,
            '回答生成中にエラーが発生しました。'
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
      navigate,
      retryAnswer,
      sessionId,
      showToast,
      submitQuestion,
      userSettings?.language,
      warmupQaIndex,
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
        title: '引用情報',
        message: `引用ID: ${citationId}`,
      })
    },
    [showToast]
  )

  return (
    <AppShell
      topbar={
        <div className="py-3 flex items-center justify-between gap-3">
          <h1 className="text-lg font-semibold">
            講義QA: {sessionId}
          </h1>
          <div className="flex gap-2">
            <Link to={`/lectures/${sessionId}/review`} className="btn btn-secondary">
              レビュー
            </Link>
            <Link to={`/lectures/${sessionId}/sources`} className="btn btn-secondary">
              ソース
            </Link>
            <Link to="/lectures" className="btn btn-secondary">
              講義一覧
            </Link>
          </div>
        </div>
      }
    >
      <div className="max-w-4xl mx-auto space-y-4">
        <form className="card p-4 space-y-3" onSubmit={handleSubmit}>
          <h2 className="font-semibold">質問を入力してください</h2>
          <textarea
            className="input min-h-24"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="講義内容について質問してください..."
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
