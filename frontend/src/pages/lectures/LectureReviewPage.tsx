/**
 * Lecture Review Page
 * Citation-grounded QA blocks with real QA APIs
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AppShell } from '@/components/common/AppShell'
import { useToast } from '@/components/common/Toast'
import { QAStreamBlocks } from '@/features/review/components/QAStreamBlocks'
import { ReviewSessionSidebar } from '@/features/review/components/ReviewSessionSidebar'
import { ReviewSourceViewer } from '@/features/review/components/ReviewSourceViewer'
import {
  mapLectureQaResponseToChunk,
  mapLectureQaResponseToDone,
} from '@/features/review/qaResponseMapper'
import {
  createReviewAnswerId,
  requestReviewQaAnswer,
  warmupReviewQaIndex,
} from '@/features/review/reviewQaApi'
import {
  buildReviewSourceFromCitation,
  DEFAULT_REVIEW_SOURCE_ITEMS,
  FALLBACK_REVIEW_SOURCE_ITEM,
} from '@/features/review/reviewSourceView'
import { useQaAnnouncer } from '@/hooks/useLiveRegion'
import { ApiError, getApiErrorMessage } from '@/lib/api/client'
import { useUserSettings } from '@/lib/api/hooks'
import { useReviewQaStore } from '@/stores/reviewQaStore'

export function LectureReviewPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const sessionId = id ?? 'demo-session'

  const { showToast } = useToast()
  const { announceQaStatus } = useQaAnnouncer()
  const { data: userSettings } = useUserSettings()
  const [question, setQuestion] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const qaTurns = useReviewQaStore((state) => state.qaTurns)
  const qaStatus = useReviewQaStore((state) => state.status)
  const selectedCitation = useReviewQaStore((state) => state.selectedCitation)
  const submitQuestion = useReviewQaStore((state) => state.submitQuestion)
  const applyChunk = useReviewQaStore((state) => state.applyChunk)
  const applyDone = useReviewQaStore((state) => state.applyDone)
  const failAnswer = useReviewQaStore((state) => state.failAnswer)
  const retryAnswer = useReviewQaStore((state) => state.retryAnswer)
  const selectCitation = useReviewQaStore((state) => state.selectCitation)
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

  const selectedCitationEntry = useMemo(() => {
    if (!selectedCitation) {
      return null
    }
    for (let turnIndex = qaTurns.length - 1; turnIndex >= 0; turnIndex -= 1) {
      const matched = qaTurns[turnIndex].citations.find(
        (citation) => citation.citationId === selectedCitation
      )
      if (matched) {
        return matched
      }
    }
    return null
  }, [qaTurns, selectedCitation])

  const activeSource = useMemo(() => {
    const defaultSource =
      DEFAULT_REVIEW_SOURCE_ITEMS[0] ?? FALLBACK_REVIEW_SOURCE_ITEM

    if (selectedCitationEntry) {
      return buildReviewSourceFromCitation(selectedCitationEntry)
    }
    if (!selectedCitation) {
      return defaultSource
    }
    return (
      DEFAULT_REVIEW_SOURCE_ITEMS.find(
        (item) => item.citationId === selectedCitation
      ) ?? defaultSource
    )
  }, [selectedCitation, selectedCitationEntry])

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

  return (
    <AppShell
      topbar={
        <div className="py-3 flex items-center justify-between gap-3">
          <h1 className="text-lg font-semibold">
            {t('review.title')}: {sessionId}
          </h1>
          <div className="flex gap-2">
            <Link to={`/lectures/${sessionId}/live`} className="btn btn-secondary">
              {t('review.actions.toLive')}
            </Link>
            <Link to="/lectures" className="btn btn-secondary">
              {t('review.actions.toLectures')}
            </Link>
          </div>
        </div>
      }
      sidebar={<ReviewSessionSidebar sessionId={sessionId} />}
      rightRail={<ReviewSourceViewer source={activeSource} />}
    >
      <div className="space-y-4">
        <form className="card p-4 space-y-3" onSubmit={handleSubmit}>
          <h2 className="font-semibold">{t('review.qa.title')}</h2>
          <textarea
            className="input min-h-24"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t('review.qa.placeholder')}
          />
          <div className="flex gap-2 items-center">
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {t('review.qa.submit')}
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
            resume: t('review.actions.resume'),
            regenerate: t('review.actions.regenerate'),
          }}
          onCitationSelect={(citationId) => {
            selectCitation(citationId)
            showToast({
              variant: 'info',
              title: 'ソース同期',
              message: `${citationId} を右ペインで表示しています。`,
            })
          }}
          onRetry={handleRetry}
          onRegenerate={handleRegenerate}
        />
      </div>
    </AppShell>
  )
}
