/**
 * Lecture Live Page
 * SSE-first live stream
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useConnectionAnnouncer, useQaAnnouncer } from '@/hooks/useLiveRegion'
import { useToast } from '@/components/common/Toast'
import { AppShell } from '@/components/common/AppShell'
import { TranscriptPanel } from '@/features/live/components/TranscriptPanel'
import { AssistPanel } from '@/features/live/components/AssistPanel'
import { SourcePanel } from '@/features/live/components/SourcePanel'
import { Tabs } from '@/components/ui'
import {
  createReviewAnswerId,
  requestReviewQaAnswer,
} from '@/features/review/reviewQaApi'
import {
  mapLectureQaResponseToChunk,
  mapLectureQaResponseToDone,
} from '@/features/review/qaResponseMapper'
import { streamClient, sseStreamTransport } from '@/lib/stream'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useReviewQaStore } from '@/stores/reviewQaStore'
import { useMicrophoneInput } from '@/features/audio/useMicrophoneInput'
import { useSpeechRecognition } from '@/features/audio/useSpeechRecognition'
import { useUserSettings } from '@/lib/api/hooks'
import { useIsMobile } from '@/hooks'
import {
  ApiError,
  demoApi,
  getApiErrorMessage,
  lectureQaApi,
} from '@/lib/api/client'
import { LIVE_FEATURE_FLAGS } from '@/lib/featureFlags'
import type { QaAnswerChunk } from '@/lib/stream/types'
import {
  mapSummaryKeyTermsToAssistTerms,
} from '@/features/live/utils/assistSupport'

const ERROR_TOAST_THROTTLE_MS = 5000
const QA_INDEX_REFRESH_INTERVAL_MS = 30000
const IDLE_AUTOSTOP_MS = LIVE_FEATURE_FLAGS.idleAutostopSeconds * 1000

type SubtitleTransformResult = {
  text: string
  status: 'translated' | 'fallback' | 'passthrough'
  fallbackReason: string | null
}

function isSubtitleTransformStatus(
  value: unknown
): value is SubtitleTransformResult['status'] {
  return (
    value === 'translated' || value === 'fallback' || value === 'passthrough'
  )
}

function sanitizeTranslatedText(
  text: string,
  mode: 'ja' | 'easy-ja' | 'en'
): string {
  const trimmed = text.trim()
  if (mode === 'en' && trimmed.startsWith('[EN]')) {
    return trimmed.replace(/^\[EN\]\s*/u, '')
  }
  return trimmed
}

function formatSubtitleId(serial: number): string {
  return `S-${String(serial).padStart(3, '0')}`
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function replaceSpeechCitationLabels(
  text: string,
  labelToSubtitleId: ReadonlyMap<string, string>
): string {
  if (!text || labelToSubtitleId.size === 0) {
    return text
  }

  let updatedText = text
  labelToSubtitleId.forEach((subtitleId, sourceLabel) => {
    const escapedLabel = escapeRegExp(sourceLabel)
    const bracketPattern = new RegExp(`\\[\\s*${escapedLabel}\\s*\\]`, 'g')
    updatedText = updatedText.replace(bracketPattern, subtitleId)
  })

  // Japanese sentences commonly omit spaces before identifier-like tokens.
  return updatedText.replace(/([ぁ-んァ-ヶ一-龠々ー])\s+(S-\d{3})/gu, '$1$2')
}

function addSubtitleIdsToSpeechCitations(
  chunk: QaAnswerChunk,
  subtitleIdByChunkId: ReadonlyMap<string, number>
): QaAnswerChunk {
  const labelToSubtitleId = new Map<string, string>()
  const citations = chunk.citations.map((citation) => {
    if (citation.type !== 'audio') {
      return citation
    }

    const parts = citation.citationId.split('::')
    const sourceChunkId = parts.length >= 2 ? parts[1] : ''
    if (!sourceChunkId) {
      return citation
    }

    const subtitleSerial = subtitleIdByChunkId.get(sourceChunkId)
    if (subtitleSerial === undefined) {
      return citation
    }

    const subtitleId = formatSubtitleId(subtitleSerial)
    const normalizedLabel = citation.label.trim()
    if (normalizedLabel && !labelToSubtitleId.has(normalizedLabel)) {
      labelToSubtitleId.set(normalizedLabel, subtitleId)
    }

    const updatedLabel = normalizedLabel
      ? `${subtitleId} (${normalizedLabel})`
      : subtitleId

    return {
      ...citation,
      label: updatedLabel,
    }
  })

  return {
    ...chunk,
    textChunk: replaceSpeechCitationLabels(chunk.textChunk, labelToSubtitleId),
    citations,
  }
}

export function LectureLivePage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const sessionId = id ?? 'session'
  const { showToast } = useToast()
  const isMobile = useIsMobile()
  const { announceConnection } = useConnectionAnnouncer()
  const { announceQaStatus } = useQaAnnouncer()
  const { data: userSettings } = useUserSettings()
  const uiLocale: 'ja' | 'en' =
    (i18n.resolvedLanguage ?? i18n.language).startsWith('en') ? 'en' : 'ja'
  const [isQaSubmitting, setIsQaSubmitting] = useState(false)

  const connection = useLiveSessionStore((state) => state.connection)
  const liveState = useLiveSessionStore((state) => state.liveState)
  const paidFeatureVisibility = useLiveSessionStore(
    (state) => state.paidFeatureVisibility
  )
  const transcriptLagMs = useLiveSessionStore((state) => state.transcriptLagMs)
  const transcriptLines = useLiveSessionStore((state) => state.transcriptLines)
  const selectedLanguage = useLiveSessionStore((state) => state.selectedLanguage)
  const setConnection = useLiveSessionStore((state) => state.setConnection)
  const setLiveState = useLiveSessionStore((state) => state.setLiveState)
  const setSessionId = useLiveSessionStore((state) => state.setSessionId)
  const applyTranscriptPartial = useLiveSessionStore((state) => state.applyTranscriptPartial)
  const applyTranscriptFinal = useLiveSessionStore((state) => state.applyTranscriptFinal)
  const applyTranslationFinal = useLiveSessionStore((state) => state.applyTranslationFinal)
  const pushSourceFrame = useLiveSessionStore((state) => state.pushSourceFrame)
  const pushSourceOcr = useLiveSessionStore((state) => state.pushSourceOcr)
  const appendAssistTerms = useLiveSessionStore((state) => state.appendAssistTerms)
  const setTranslationFallbackActive = useLiveSessionStore(
    (state) => state.setTranslationFallbackActive
  )
  const hydrateFromSettings = useLiveSessionStore((state) => state.hydrateFromSettings)
  const resetLiveData = useLiveSessionStore((state) => state.resetLiveData)
  const qaTurns = useReviewQaStore((state) => state.qaTurns)
  const qaStatus = useReviewQaStore((state) => state.status)
  const submitQuestion = useReviewQaStore((state) => state.submitQuestion)
  const applyChunk = useReviewQaStore((state) => state.applyChunk)
  const applyDone = useReviewQaStore((state) => state.applyDone)
  const failAnswer = useReviewQaStore((state) => state.failAnswer)
  const retryAnswer = useReviewQaStore((state) => state.retryAnswer)
  const resetReviewQa = useReviewQaStore((state) => state.reset)
  const previousSessionIdRef = useRef<string | null>(null)
  const successfulTurnCountRef = useRef(0)
  const lastQaIndexBuildAtRef = useRef(0)
  const qaIndexBuiltOnceRef = useRef(false)
  const previousConnectionRef = useRef(connection)
  const lastReconnectToastAtRef = useRef(0)
  const lastErrorToastAtRef = useRef(0)
  const lastTranslationFallbackToastAtRef = useRef(0)
  const didFinalizeSessionRef = useRef(false)
  const lastInteractionAtRef = useRef(Date.now())
  const lastSubtitleAtRef = useRef(Date.now())
  const liveStateRef = useRef(liveState)
  const sessionIdRef = useRef(sessionId)

  const markInteraction = useCallback(() => {
    lastInteractionAtRef.current = Date.now()
  }, [])

  useEffect(() => {
    liveStateRef.current = liveState
  }, [liveState])

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  const notifyTranslationFallback = useCallback(
    (mode: 'easy-ja' | 'en', reason: string | null) => {
      const nowMs = Date.now()
      if (
        nowMs - lastTranslationFallbackToastAtRef.current <
        ERROR_TOAST_THROTTLE_MS
      ) {
        return
      }
      lastTranslationFallbackToastAtRef.current = nowMs
      showToast({
        variant: 'warning',
        title: t('live.messages.translationFallbackTitle'),
        message:
          mode === 'en'
            ? t('live.messages.translationFallbackEn')
            : t('live.messages.translationFallbackEasyJa'),
      })
      console.warn('[subtitle-translation] fallback in use', {
        sessionId,
        mode,
        reason,
      })
    },
    [sessionId, showToast, t]
  )

  const transformSubtitleForMode = useCallback(
    async (
      text: string,
      mode: 'ja' | 'easy-ja' | 'en'
    ): Promise<SubtitleTransformResult> => {
      const normalizedText = text.trim()
      if (!normalizedText || mode === 'ja') {
        return {
          text: normalizedText,
          status: 'passthrough',
          fallbackReason: null,
        }
      }
      if (
        !paidFeatureVisibility.translation ||
        liveState !== 'running' ||
        document.visibilityState !== 'visible'
      ) {
        return {
          text: normalizedText,
          status: 'fallback',
          fallbackReason: !paidFeatureVisibility.translation
            ? 'feature_disabled'
            : document.visibilityState !== 'visible'
              ? 'page_hidden'
              : 'session_inactive',
        }
      }

      try {
        const transformed = await demoApi.transformSubtitle({
          session_id: sessionId,
          text: normalizedText,
          target_lang_mode: mode,
        })
        const sanitized = sanitizeTranslatedText(
          transformed.transformed_text || '',
          mode
        )
        if (!isSubtitleTransformStatus(transformed.status)) {
          const inferredTranslated =
            sanitized.length > 0 && sanitized !== normalizedText
          return {
            text: sanitized || normalizedText,
            status: inferredTranslated ? 'translated' : 'fallback',
            fallbackReason: inferredTranslated
              ? null
              : 'missing_transform_status',
          }
        }
        if (transformed.status === 'translated' && !sanitized) {
          return {
            text: normalizedText,
            status: 'fallback',
            fallbackReason: 'empty_transformed_text',
          }
        }
        return {
          text: sanitized || normalizedText,
          status: transformed.status,
          fallbackReason: transformed.fallback_reason ?? null,
        }
      } catch (error) {
        console.warn('[subtitle-translation] request failed', {
          sessionId,
          mode,
          error,
        })
        return {
          text: normalizedText,
          status: 'fallback',
          fallbackReason: 'client_request_failed',
        }
      }
    },
    [liveState, paidFeatureVisibility.translation, sessionId]
  )

  const refreshQaIndexIfNeeded = useCallback(async () => {
    if (!paidFeatureVisibility.qa || liveState !== 'running') {
      return
    }
    const now = Date.now()
    const elapsed = now - lastQaIndexBuildAtRef.current
    if (elapsed < QA_INDEX_REFRESH_INTERVAL_MS) {
      return
    }

    try {
      await lectureQaApi.buildIndex({
        session_id: sessionId,
        rebuild: true,
      })
      lastQaIndexBuildAtRef.current = now
      qaIndexBuiltOnceRef.current = true
    } catch (error) {
      if (qaIndexBuiltOnceRef.current) {
        showToast({
          variant: 'warning',
          title: t('live.messages.qaIndexRefreshFailedTitle'),
          message: getApiErrorMessage(
            error,
            t('live.messages.qaIndexRefreshFailedMessage')
          ),
        })
        return
      }
      throw error
    }
  }, [liveState, paidFeatureVisibility.qa, sessionId, showToast, t])

  const executeMiniQuestion = useCallback(
    async (
      rawQuestion: string,
      options: { existingAnswerId?: string } = {}
    ) => {
      const normalizedQuestion = rawQuestion.trim()
      if (
        !normalizedQuestion ||
        isQaSubmitting ||
        !paidFeatureVisibility.qa ||
        liveState !== 'running'
      ) {
        return
      }

      const answerId = options.existingAnswerId ?? createReviewAnswerId()
      setIsQaSubmitting(true)

      if (options.existingAnswerId) {
        retryAnswer(answerId)
      } else {
        submitQuestion(normalizedQuestion, answerId)
      }

      const locale = uiLocale
      announceQaStatus('generating', locale)

      try {
        await refreshQaIndexIfNeeded()
        const response = await requestReviewQaAnswer({
          sessionId,
          question: normalizedQuestion,
          language: selectedLanguage,
          hasSuccessfulTurn: successfulTurnCountRef.current > 0,
        })

        const subtitleIdByChunkId = new Map<string, number>()
        transcriptLines.forEach((line) => {
          if (typeof line.subtitleSerial === 'number' && !line.isPartial) {
            subtitleIdByChunkId.set(line.id, line.subtitleSerial)
          }
        })

        const mappedChunk = mapLectureQaResponseToChunk(answerId, response)
        applyChunk(
          addSubtitleIdsToSpeechCitations(mappedChunk, subtitleIdByChunkId)
        )
        applyDone(mapLectureQaResponseToDone(answerId))
        successfulTurnCountRef.current += 1
        announceQaStatus('done', locale)

        if (response.fallback) {
          showToast({
            variant: 'warning',
            title: t('live.messages.insufficientEvidenceTitle'),
            message: response.action_next,
          })
        }
      } catch (error) {
        failAnswer(answerId)
        announceQaStatus('error', locale)

        if (error instanceof ApiError && error.status === 401) {
          showToast({
            variant: 'danger',
            title: t('live.messages.authErrorTitle'),
            message: t('live.messages.authErrorMessage'),
          })
          return
        }
        if (error instanceof ApiError && error.status === 404) {
          showToast({
            variant: 'danger',
            title: t('live.messages.sessionNotFoundTitle'),
            message: t('live.messages.sessionNotFoundMessage'),
          })
          navigate('/lectures')
          return
        }
        if (error instanceof ApiError && error.status === 503) {
          showToast({
            variant: 'danger',
            title: t('live.messages.qaUnavailableTitle'),
            message: t('live.messages.qaUnavailableMessage'),
          })
          return
        }
        showToast({
          variant: 'danger',
          title: t('live.messages.answerFetchFailedTitle'),
          message: getApiErrorMessage(
            error,
            t('live.messages.answerFetchFailedMessage')
          ),
        })
      } finally {
        setIsQaSubmitting(false)
      }
    },
    [
      announceQaStatus,
      applyChunk,
      applyDone,
      failAnswer,
      isQaSubmitting,
      navigate,
      refreshQaIndexIfNeeded,
      retryAnswer,
      sessionId,
      showToast,
      submitQuestion,
      t,
      transcriptLines,
      uiLocale,
      selectedLanguage,
      paidFeatureVisibility.qa,
      liveState,
    ]
  )

  const handleMiniQuestion = useCallback(
    (question: string) => {
      markInteraction()
      void executeMiniQuestion(question)
    },
    [executeMiniQuestion, markInteraction]
  )

  const handleQaRetry = useCallback(
    (answerId: string) => {
      if (isQaSubmitting) {
        return
      }
      const turn = qaTurns.find((item) => item.answerId === answerId)
      if (!turn) {
        return
      }
      markInteraction()
      void executeMiniQuestion(turn.question, { existingAnswerId: answerId })
    },
    [executeMiniQuestion, isQaSubmitting, markInteraction, qaTurns]
  )

  const handleQaRegenerate = useCallback(
    (question: string) => {
      if (isQaSubmitting) {
        return
      }
      markInteraction()
      void executeMiniQuestion(question)
    },
    [executeMiniQuestion, isQaSubmitting, markInteraction]
  )

  const handleQaCitationSelect = useCallback(
    (citationId: string) => {
      markInteraction()
      showToast({
        variant: 'info',
        title: t('live.messages.citationInfoTitle'),
        message: t('live.messages.citationInfoMessage', { citationId }),
      })
    },
    [markInteraction, showToast, t]
  )

  const handleSpeechResult = useCallback(
    async (transcript: string, isFinal: boolean) => {
      if (
        !isFinal ||
        !transcript.trim() ||
        liveState !== 'running' ||
        didFinalizeSessionRef.current
      ) {
        return
      }

      const rawTranscript = transcript.trim()

      const now = Date.now()
      const startMs = now
      const endMs = now + 2000 // 2秒間と仮定
      lastSubtitleAtRef.current = now

      // バックエンドに送信（SSE経由で表示）
      try {
        const ingested = await demoApi.ingestSpeechChunk({
          session_id: sessionId,
          start_ms: Math.floor(startMs / 1000) * 1000,
          end_ms: Math.floor(endMs / 1000) * 1000,
          text: rawTranscript,
          confidence: 0.9,
          is_final: true,
          speaker: 'teacher',
        })

        applyTranscriptFinal({
          id: ingested.event_id,
          tsStartMs: Math.floor(startMs / 1000) * 1000,
          tsEndMs: Math.floor(endMs / 1000) * 1000,
          speakerLabel: 'teacher',
          sourceLangText: rawTranscript,
          originalLangText: rawTranscript,
          confidence: 0.9,
          isPartial: false,
          sourceRefs: {
            audioSegmentId: ingested.event_id,
            sourceFrameIds: [],
          },
        })

        // やさしい日本語・英語は原文を翻訳元にする。
        const currentMode = useLiveSessionStore.getState().selectedLanguage
        if (paidFeatureVisibility.translation && currentMode !== 'ja') {
          const transformed = await transformSubtitleForMode(
            rawTranscript,
            currentMode
          )
          applyTranslationFinal(
            ingested.event_id,
            transformed.text,
            currentMode,
            transformed.status
          )
          if (transformed.status === 'fallback') {
            setTranslationFallbackActive(true)
            notifyTranslationFallback(currentMode, transformed.fallbackReason)
          }
        }

        // 専門用語を分析して用語サポートを更新（トグルONの場合のみ）
        if (
          paidFeatureVisibility.keyterms &&
          useLiveSessionStore.getState().keytermsEnabled
        ) {
          try {
            const langMode = useLiveSessionStore.getState().langMode
            const keytermsResult = await demoApi.analyzeKeyterms({
              session_id: sessionId,
              transcript_text: rawTranscript,
              lang_mode: langMode,
            })

            // 用語サポートを更新
            if (keytermsResult.status === 'ok' && keytermsResult.key_terms.length > 0) {
              appendAssistTerms(mapSummaryKeyTermsToAssistTerms(keytermsResult.key_terms))
            } else if (keytermsResult.status !== 'ok') {
              console.info('[keyterms] ingest trigger non-ok status', {
                sessionId,
                status: keytermsResult.status,
                reason: keytermsResult.reason,
              })
            }
          } catch (keytermsError) {
            // 専門用語分析が失敗しても、字幕自体は正常に処理されたのでエラーは無視
            console.warn('Key terms analysis failed:', keytermsError)
          }
        }

      } catch (error) {
        const nowMs = Date.now()
        if (nowMs - lastErrorToastAtRef.current < ERROR_TOAST_THROTTLE_MS) {
          return
        }
        lastErrorToastAtRef.current = nowMs
        showToast({
          variant: 'danger',
          title: t('live.messages.audioSyncErrorTitle'),
          message: getApiErrorMessage(error, t('live.messages.audioSyncErrorMessage')),
        })
      }
    },
    [
      sessionId,
      liveState,
      applyTranscriptFinal,
      applyTranslationFinal,
      showToast,
      appendAssistTerms,
      setTranslationFallbackActive,
      notifyTranslationFallback,
      t,
      transformSubtitleForMode,
      paidFeatureVisibility.keyterms,
      paidFeatureVisibility.translation,
    ]
  )

  const handleSpeechError = useCallback(
    (error: string) => {
      console.error('Speech recognition error:', error)
    },
    []
  )

  // 仕様: 入力は常に日本語ASR。表示言語(ja/easy-ja/en)とは独立させる。
  const speechRecognitionLang = 'ja-JP'

  const { isSupported: speechSupported, startListening, stopListening } =
    useSpeechRecognition({
      lang: speechRecognitionLang,
      continuous: true,
      interimResults: true,
      onResult: handleSpeechResult,
      onError: handleSpeechError,
    })

  const { isRecording, audioLevel, lastError, startRecording, stopRecording } =
    useMicrophoneInput()

  const finalizeLiveSession = useCallback(
    async ({
      reason,
      requestFinalize = true,
      keepalive = false,
      suppressErrorToast = false,
    }: {
      reason: string
      requestFinalize?: boolean
      keepalive?: boolean
      suppressErrorToast?: boolean
    }) => {
      if (didFinalizeSessionRef.current) {
        return
      }

      didFinalizeSessionRef.current = true
      setLiveState('stopping')
      setConnection('idle')
      streamClient.disconnect()
      stopListening()
      stopRecording()

      if (requestFinalize) {
        try {
          if (keepalive) {
            demoApi.finalizeDemoSessionKeepalive(sessionId)
          } else {
            await demoApi.finalizeDemoSession(sessionId)
          }
        } catch (error) {
          const status = error instanceof ApiError ? error.status : undefined
          if (status !== 404 && status !== 409 && !suppressErrorToast) {
            showToast({
              variant: 'warning',
              title: t('lectures.messages.sessionFinalizeFailed'),
              message: getApiErrorMessage(
                error,
                t('lectures.messages.sessionFinalizeApiFailed')
              ),
            })
          }
        }
      }

      setLiveState('ended')
      setConnection('idle')

      if (reason === 'manual') {
        showToast({
          variant: 'success',
          title: t('lectures.messages.sessionFinalized'),
        })
      }
    },
    [
      sessionId,
      setConnection,
      setLiveState,
      stopListening,
      stopRecording,
      showToast,
      t,
    ]
  )

  const connectStream = useCallback(() => {
    if (document.visibilityState !== 'visible') {
      return
    }
    streamClient.connect(sessionId).catch((error) => {
      showToast({
        variant: 'warning',
        title: t('live.messages.sseConnectFailedTitle'),
        message: `${getApiErrorMessage(error, t('live.messages.sseConnectFailedMessage'))} ${t('live.messages.autoReconnectMessage')}`,
      })
    })
  }, [sessionId, showToast, t])

  const startLiveCapture = useCallback(async () => {
    if (liveState !== 'idle' || didFinalizeSessionRef.current) {
      return
    }

    didFinalizeSessionRef.current = false
    lastInteractionAtRef.current = Date.now()
    lastSubtitleAtRef.current = Date.now()
    setSessionId(sessionId)
    setConnection('connecting')
    setLiveState('running')
    await startRecording()

    if (!useLiveSessionStore.getState().paidFeatureVisibility.translation) {
      setTranslationFallbackActive(false)
    }

    if (!useLiveSessionStore.getState().summaryEnabled) {
      useLiveSessionStore.getState().setAssistSummary({
        timestampMs: Date.now(),
        points: [],
      })
    }

    streamClient.setTransport(sseStreamTransport)
    connectStream()
  }, [
    connectStream,
    liveState,
    sessionId,
    setConnection,
    setLiveState,
    setSessionId,
    setTranslationFallbackActive,
    startRecording,
  ])

  // 音声認識の開始/停止を録音状態に同期
  useEffect(() => {
    if (isRecording && speechSupported) {
      startListening()
    } else {
      stopListening()
    }
  }, [isRecording, speechSupported, startListening, stopListening])

  useEffect(() => {
    if (!isRecording || !speechSupported) {
      return
    }
    stopListening()
    const timer = window.setTimeout(() => {
      startListening()
    }, 150)
    return () => window.clearTimeout(timer)
  }, [isRecording, speechSupported, speechRecognitionLang, startListening, stopListening])

  useEffect(() => {
    resetReviewQa()
    successfulTurnCountRef.current = 0
    lastQaIndexBuildAtRef.current = 0
    qaIndexBuiltOnceRef.current = false
    return () => {
      resetReviewQa()
    }
  }, [resetReviewQa, sessionId])

  useEffect(() => {
    hydrateFromSettings({
      language: userSettings?.language,
      transcriptDensity: userSettings?.transcriptDensity,
      autoScrollDefault: userSettings?.autoScrollDefault,
    })
  }, [hydrateFromSettings, userSettings])

  useEffect(() => {
    const previousSessionId = previousSessionIdRef.current
    if (previousSessionId && previousSessionId !== sessionId) {
      if (!didFinalizeSessionRef.current && liveState === 'running') {
        demoApi.finalizeDemoSessionKeepalive(previousSessionId)
      }
      streamClient.disconnect()
      stopListening()
      stopRecording()
      resetLiveData()
      setSessionId(null)
      didFinalizeSessionRef.current = false
    }
    previousSessionIdRef.current = sessionId
  }, [liveState, resetLiveData, sessionId, setSessionId, stopListening, stopRecording])

  useEffect(() => {
    streamClient.setTransport(sseStreamTransport)
    const subscriptions = [
      streamClient.subscribe('session.status', (event) => {
        setConnection(event.payload.connection)
        announceConnection(event.payload.connection, uiLocale)

        const previous = previousConnectionRef.current
        const current = event.payload.connection
        if ((previous === 'reconnecting' || previous === 'error') && current === 'live') {
          showToast({
            variant: 'success',
            title: t('live.messages.reconnectedTitle'),
            message: t('live.messages.reconnectedMessage'),
          })
        } else if (current === 'reconnecting') {
          const now = Date.now()
          if (now - lastReconnectToastAtRef.current >= ERROR_TOAST_THROTTLE_MS) {
            lastReconnectToastAtRef.current = now
            showToast({
              variant: 'warning',
              title: t('live.messages.reconnectingTitle'),
              message: t('live.messages.reconnectingMessage'),
            })
          }
        }
        if (
          current === 'degraded' &&
          useLiveSessionStore.getState().liveState === 'running'
        ) {
          void finalizeLiveSession({
            reason: 'server_finalized',
            requestFinalize: false,
            suppressErrorToast: true,
          })
        }
        previousConnectionRef.current = current
      }),
      streamClient.subscribe('transcript.partial', (event) => applyTranscriptPartial(event.payload)),
      streamClient.subscribe('transcript.final', (event) => {
        lastSubtitleAtRef.current = Date.now()
        applyTranscriptFinal(event.payload)
        const currentMode = useLiveSessionStore.getState().selectedLanguage
        if (
          paidFeatureVisibility.translation &&
          currentMode !== 'ja' &&
          document.visibilityState === 'visible'
        ) {
          // Only translate if this line doesn't already have a translation
          // for the current display mode. SSE re-delivers events on reconnect
          // and the redundant transform API calls can return fallback (Japanese)
          // text that overwrites a valid earlier translation.
          const existingLine = useLiveSessionStore.getState().transcriptLines.find(
            (l) => l.id === event.payload.id
          )
          if (
            existingLine?.translatedLangMode === currentMode &&
            existingLine.translationStatus !== 'fallback'
          ) {
            return
          }
          void (async () => {
            const transformed = await transformSubtitleForMode(
              event.payload.sourceLangText,
              currentMode
            )
            applyTranslationFinal(
              event.payload.id,
              transformed.text,
              currentMode,
              transformed.status
            )
            if (transformed.status === 'fallback') {
              setTranslationFallbackActive(true)
              notifyTranslationFallback(currentMode, transformed.fallbackReason)
            }
          })()
        }
      }),
      // 翻訳は /subtitle/transform の結果を正として扱う。
      // 旧経路の translation.final が届いても字幕を上書きしない。
      streamClient.subscribe('source.frame', (event) => pushSourceFrame(event.payload)),
      streamClient.subscribe('source.ocr', (event) => pushSourceOcr(event.payload)),
      streamClient.subscribe('assist.term', (event) => {
        if (paidFeatureVisibility.keyterms) {
          appendAssistTerms(event.payload)
        }
      }),
      streamClient.subscribe('error', (event) => {
        showToast({
          variant: event.payload.recoverable ? 'warning' : 'danger',
          title: t('live.messages.liveEventErrorTitle'),
          message: event.payload.message,
        })
      }),
    ]

    return () => {
      subscriptions.forEach((unsubscribe) => unsubscribe())
    }
  }, [
    announceConnection,
    applyTranscriptFinal,
    applyTranscriptPartial,
    applyTranslationFinal,
    pushSourceFrame,
    pushSourceOcr,
    appendAssistTerms,
    finalizeLiveSession,
    paidFeatureVisibility.keyterms,
    paidFeatureVisibility.translation,
    setConnection,
    setTranslationFallbackActive,
    showToast,
    t,
    uiLocale,
    notifyTranslationFallback,
    transformSubtitleForMode,
    connectStream,
  ])

  useEffect(() => {
    if (liveState !== 'running') {
      return
    }

    const recordInteraction = () => {
      markInteraction()
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        void finalizeLiveSession({
          reason: 'visibility_hidden',
          suppressErrorToast: true,
        })
        return
      }
      recordInteraction()
    }

    const handleKeepaliveFinalize = () => {
      void finalizeLiveSession({
        reason: 'pagehide',
        keepalive: true,
        suppressErrorToast: true,
      })
    }

    const checkIdleTimeout = () => {
      const now = Date.now()
      if (now - lastInteractionAtRef.current >= IDLE_AUTOSTOP_MS) {
        void finalizeLiveSession({
          reason: 'inactive_user',
          suppressErrorToast: true,
        })
        return
      }
      if (now - lastSubtitleAtRef.current >= IDLE_AUTOSTOP_MS) {
        void finalizeLiveSession({
          reason: 'inactive_subtitle',
          suppressErrorToast: true,
        })
      }
    }

    window.addEventListener('pointerdown', recordInteraction, { passive: true })
    window.addEventListener('keydown', recordInteraction)
    window.addEventListener('touchstart', recordInteraction, { passive: true })
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('pagehide', handleKeepaliveFinalize)
    window.addEventListener('beforeunload', handleKeepaliveFinalize)

    const timer = window.setInterval(checkIdleTimeout, 5000)

    return () => {
      window.removeEventListener('pointerdown', recordInteraction)
      window.removeEventListener('keydown', recordInteraction)
      window.removeEventListener('touchstart', recordInteraction)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('pagehide', handleKeepaliveFinalize)
      window.removeEventListener('beforeunload', handleKeepaliveFinalize)
      window.clearInterval(timer)
    }
  }, [finalizeLiveSession, liveState, markInteraction])

  useEffect(() => {
    return () => {
      if (!didFinalizeSessionRef.current && liveStateRef.current === 'running') {
        demoApi.finalizeDemoSessionKeepalive(sessionIdRef.current)
      }
      streamClient.disconnect()
      stopListening()
      stopRecording()
      resetLiveData()
      setSessionId(null)
      previousSessionIdRef.current = null
      didFinalizeSessionRef.current = false
    }
  }, [resetLiveData, setSessionId, stopListening, stopRecording])

  useEffect(() => {
    if (!lastError) {
      return
    }
    showToast({ variant: 'danger', title: t('live.messages.micErrorTitle'), message: lastError })
  }, [lastError, showToast, t])

  useEffect(() => {
    if (selectedLanguage !== 'ja' && paidFeatureVisibility.translation) {
      return
    }
    setTranslationFallbackActive(false)
  }, [paidFeatureVisibility.translation, selectedLanguage, setTranslationFallbackActive])

  useEffect(() => {
    if (
      selectedLanguage === 'ja' ||
      !paidFeatureVisibility.translation ||
      liveState !== 'running' ||
      document.visibilityState !== 'visible'
    ) {
      return
    }

    // Read transcript lines non-reactively to avoid re-triggering on every
    // translation update (applyTranslationFinal mutates transcriptLines).
    const lines = useLiveSessionStore.getState().transcriptLines
    if (lines.length === 0) {
      return
    }

    lines.forEach((line) => {
      if (
        line.translatedLangMode === selectedLanguage &&
        line.translationStatus !== 'fallback'
      ) {
        return
      }
      void (async () => {
        const transformed = await transformSubtitleForMode(
          line.sourceLangText,
          selectedLanguage
        )
        applyTranslationFinal(
          line.id,
          transformed.text,
          selectedLanguage,
          transformed.status
        )
        if (transformed.status === 'fallback') {
          setTranslationFallbackActive(true)
          notifyTranslationFallback(selectedLanguage, transformed.fallbackReason)
        }
      })()
    })
  }, [
    applyTranslationFinal,
    liveState,
    notifyTranslationFallback,
    paidFeatureVisibility.translation,
    selectedLanguage,
    setTranslationFallbackActive,
    transformSubtitleForMode,
  ])

  const CONNECTION_LABELS: Record<string, string> = {
    idle: t('live.connection.idle'),
    connecting: t('live.connection.connecting'),
    live: t('live.connection.live'),
    reconnecting: t('live.connection.reconnecting'),
    degraded: t('live.connection.degraded'),
    error: t('live.connection.error'),
  }

  const CONNECTION_BADGE: Record<string, string> = {
    idle: 'badge-muted',
    connecting: 'badge-warning',
    live: 'badge-live',
    reconnecting: 'badge-warning',
    degraded: 'badge-warning',
    error: 'badge-danger',
  }

  const connectionBadgeClass =
    liveState === 'running'
      ? CONNECTION_BADGE[connection] ?? 'badge-muted'
      : liveState === 'stopping'
        ? 'badge-warning'
        : liveState === 'ended'
          ? 'badge-default'
          : CONNECTION_BADGE.idle
  const connectionLabel =
    liveState === 'running'
      ? CONNECTION_LABELS[connection] ?? connection
      : liveState === 'stopping'
        ? t('lectures.actions.finalizing')
        : liveState === 'ended'
          ? t('lectures.status.ended')
          : CONNECTION_LABELS.idle
  const primaryButtonLabel =
    liveState === 'running'
      ? t('lectures.actions.finalize')
      : liveState === 'stopping'
        ? t('lectures.actions.finalizing')
        : liveState === 'ended'
          ? t('lectures.status.ended')
          : t('live.stream.startRecording')
  const primaryButtonClass =
    liveState === 'running' ? 'btn-secondary' : 'btn-primary'
  const primaryButtonDisabled =
    liveState === 'stopping' || liveState === 'ended'

  const audioBarCount = 5
  const filledBars = Math.round(audioLevel * audioBarCount)
  const shortSessionId = sessionId.length > 8 ? `${sessionId.slice(0, 8)}…` : sessionId
  const assistPanel = (
    <AssistPanel
      onAskMiniQuestion={handleMiniQuestion}
      qaTurns={qaTurns}
      qaStatus={qaStatus}
      isQaSubmitting={isQaSubmitting}
      onQaCitationSelect={handleQaCitationSelect}
      onQaRetry={handleQaRetry}
      onQaRegenerate={handleQaRegenerate}
    />
  )

  return (
    <AppShell
      topbar={
        <div className="flex flex-col gap-3 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold">{t('live.stream.title')}</h1>
            <span
              className={`badge ${connectionBadgeClass}`}
              title={t('live.aria.sessionIdTitle', { sessionId })}
            >
              {connectionLabel}
            </span>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-fg-secondary hover:text-fg-primary transition-colors"
              title={sessionId}
              onClick={() => navigator.clipboard.writeText(sessionId)}
              aria-label={t('live.aria.copySessionId')}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {shortSessionId}
            </button>
            {transcriptLagMs > 300 && (
              <span className="text-xs text-warning" title={t('live.aria.transcriptLag')}>⚠️ {transcriptLagMs}ms</span>
            )}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <button
              type="button"
              className={`btn w-full sm:w-auto ${primaryButtonClass}`}
              onClick={() => {
                markInteraction()
                if (liveState === 'running') {
                  void finalizeLiveSession({ reason: 'manual' })
                  return
                }
                if (liveState === 'idle') {
                  void startLiveCapture()
                }
              }}
              disabled={primaryButtonDisabled}
            >
              {primaryButtonLabel}
            </button>
            {/* Audio level bars */}
            <div
              className="flex items-end gap-0.5 h-5"
              aria-label={t('live.aria.inputLevel', { value: Math.round(audioLevel * 100) })}
              title={t('live.aria.inputLevel', { value: Math.round(audioLevel * 100) })}
            >
              {Array.from({ length: audioBarCount }, (_, i) => (
                <div
                  key={i}
                  className="w-1 rounded-sm transition-all duration-100"
                  style={{
                    height: `${((i + 1) / audioBarCount) * 100}%`,
                    backgroundColor: i < filledBars ? 'var(--color-success)' : 'var(--color-border)',
                  }}
                />
              ))}
            </div>
            <Link
              to="/lectures"
              className="btn btn-secondary w-full sm:w-auto"
            >
              {t('nav.lectures')}
            </Link>
          </div>
        </div>
      }
      rightRail={!isMobile ? <div className="space-y-4">{assistPanel}<SourcePanel /></div> : undefined}
    >
      {isMobile ? (
        <Tabs
          defaultTab="transcript"
          tabs={[
            {
              value: 'transcript',
              label: t('live.stream.title'),
              content: (
                <div className="h-[calc(100vh-210px)] min-h-[24rem]">
                  <TranscriptPanel />
                </div>
              ),
            },
            {
              value: 'assist',
              label: t('assistPanel.sections.qa'),
              content: assistPanel,
            },
            {
              value: 'sources',
              label: t('sourcePanel.title'),
              content: <SourcePanel />,
            },
          ]}
        />
      ) : (
        <div className="h-[calc(100vh-130px)]">
          <TranscriptPanel />
        </div>
      )}
    </AppShell>
  )
}
