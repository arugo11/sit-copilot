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
import { useAudioInputStore } from '@/stores/audioInputStore'
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
import type { QaAnswerChunk } from '@/lib/stream/types'
import {
  mapSummaryKeyTermsToAssistTerms,
} from '@/features/live/utils/assistSupport'

const ERROR_TOAST_THROTTLE_MS = 5000
const QA_INDEX_REFRESH_INTERVAL_MS = 30000

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
  const transcriptLagMs = useLiveSessionStore((state) => state.transcriptLagMs)
  const transcriptLines = useLiveSessionStore((state) => state.transcriptLines)
  const selectedLanguage = useLiveSessionStore((state) => state.selectedLanguage)
  const setConnection = useLiveSessionStore((state) => state.setConnection)
  const setSessionId = useLiveSessionStore((state) => state.setSessionId)
  const applyTranscriptPartial = useLiveSessionStore((state) => state.applyTranscriptPartial)
  const applyTranscriptFinal = useLiveSessionStore((state) => state.applyTranscriptFinal)
  const replaceTranscriptLineText = useLiveSessionStore(
    (state) => state.replaceTranscriptLineText
  )
  const setTranscriptCorrectionStatus = useLiveSessionStore(
    (state) => state.setTranscriptCorrectionStatus
  )
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
  const autoStartedSessionIdRef = useRef<string | null>(null)
  const previousSessionIdRef = useRef<string | null>(null)
  const successfulTurnCountRef = useRef(0)
  const lastQaIndexBuildAtRef = useRef(0)
  const qaIndexBuiltOnceRef = useRef(false)
  const resumeRecordingOnVisibleRef = useRef(false)
  const previousConnectionRef = useRef(connection)
  const lastReconnectToastAtRef = useRef(0)
  const lastErrorToastAtRef = useRef(0)
  const lastTranslationFallbackToastAtRef = useRef(0)

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
    [sessionId]
  )

  const refreshQaIndexIfNeeded = useCallback(async () => {
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
  }, [sessionId, showToast, t])

  const executeMiniQuestion = useCallback(
    async (
      rawQuestion: string,
      options: { existingAnswerId?: string } = {}
    ) => {
      const normalizedQuestion = rawQuestion.trim()
      if (!normalizedQuestion || isQaSubmitting) {
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
    ]
  )

  const handleMiniQuestion = useCallback(
    (question: string) => {
      void executeMiniQuestion(question)
    },
    [executeMiniQuestion]
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
      void executeMiniQuestion(turn.question, { existingAnswerId: answerId })
    },
    [executeMiniQuestion, isQaSubmitting, qaTurns]
  )

  const handleQaRegenerate = useCallback(
    (question: string) => {
      if (isQaSubmitting) {
        return
      }
      void executeMiniQuestion(question)
    },
    [executeMiniQuestion, isQaSubmitting]
  )

  const handleQaCitationSelect = useCallback(
    (citationId: string) => {
      showToast({
        variant: 'info',
        title: t('live.messages.citationInfoTitle'),
        message: t('live.messages.citationInfoMessage', { citationId }),
      })
    },
    [showToast, t]
  )

  const handleSpeechResult = useCallback(
    async (transcript: string, isFinal: boolean) => {
      if (!isFinal || !transcript.trim()) {
        return
      }

      const rawTranscript = transcript.trim()

      const now = Date.now()
      const startMs = now
      const endMs = now + 2000 // 2秒間と仮定

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

        let transcriptForAssist = rawTranscript
        setTranscriptCorrectionStatus(ingested.event_id, 'pending')
        const correctionStartedAt = performance.now()
        console.debug('[subtitle-correction] start', {
          sessionId,
          eventId: ingested.event_id,
        })

        try {
          const pendingMinDuration = new Promise<void>((resolve) => {
            window.setTimeout(() => resolve(), 300)
          })
          const audited = await demoApi.auditAndApplySpeechChunk({
            session_id: sessionId,
            event_id: ingested.event_id,
          })
          await pendingMinDuration
          console.debug('[subtitle-correction] success', {
            sessionId,
            eventId: ingested.event_id,
            elapsedMs: Math.round(performance.now() - correctionStartedAt),
            correctedText: audited.corrected_text,
            reviewStatus: audited.review_status,
            wasCorrected: audited.was_corrected,
          })
          if (audited.review_status === 'reviewed') {
            setTranscriptCorrectionStatus(ingested.event_id, 'reviewed')
          } else {
            setTranscriptCorrectionStatus(ingested.event_id, 'review_failed')
          }
          if (audited.was_corrected && audited.corrected_text.trim()) {
            transcriptForAssist = audited.corrected_text.trim()
            replaceTranscriptLineText(ingested.event_id, transcriptForAssist)
          }
        } catch (auditError) {
          console.warn('[subtitle-correction] audit-apply failed', {
            sessionId,
            eventId: ingested.event_id,
            elapsedMs: Math.round(performance.now() - correctionStartedAt),
            error: auditError,
          })

          setTranscriptCorrectionStatus(ingested.event_id, 'review_failed')
          console.warn('Post-display subtitle audit failed:', auditError)
        }

        // やさしい日本語・英語は、補正後テキスト（存在する場合）を翻訳元にする
        const currentMode = useLiveSessionStore.getState().selectedLanguage
        if (currentMode !== 'ja') {
          const transformed = await transformSubtitleForMode(
            transcriptForAssist,
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
        if (useLiveSessionStore.getState().keytermsEnabled) {
          try {
            const langMode = useLiveSessionStore.getState().langMode
            const keytermsResult = await demoApi.analyzeKeyterms({
              session_id: sessionId,
              transcript_text: transcriptForAssist,
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
      applyTranscriptFinal,
      applyTranslationFinal,
      replaceTranscriptLineText,
      setTranscriptCorrectionStatus,
      showToast,
      appendAssistTerms,
      setTranslationFallbackActive,
      notifyTranslationFallback,
      t,
      transformSubtitleForMode,
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
      stopRecording()
      resetLiveData()
      setSessionId(null)
    }
    previousSessionIdRef.current = sessionId
  }, [resetLiveData, sessionId, setSessionId, stopRecording])

  useEffect(() => {
    if (document.visibilityState !== 'visible') {
      return
    }
    if (isRecording || autoStartedSessionIdRef.current === sessionId) {
      return
    }
    autoStartedSessionIdRef.current = sessionId
    setSessionId(sessionId)
    void startRecording()
  }, [isRecording, startRecording, sessionId, setSessionId])

  useEffect(() => {
    const pauseLiveSession = () => {
      const wasRecording = useAudioInputStore.getState().isRecording
      resumeRecordingOnVisibleRef.current = wasRecording
      if (wasRecording) {
        stopRecording()
      }
      streamClient.disconnect()
    }

    const resumeLiveSession = () => {
      connectStream()
      if (!resumeRecordingOnVisibleRef.current) {
        return
      }
      resumeRecordingOnVisibleRef.current = false
      void startRecording()
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        pauseLiveSession()
        return
      }
      if (document.visibilityState === 'visible') {
        resumeLiveSession()
      }
    }

    const handlePageHide = () => {
      pauseLiveSession()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('pagehide', handlePageHide)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('pagehide', handlePageHide)
    }
  }, [connectStream, startRecording, stopRecording])

  useEffect(() => {
    const subscriptions = [
      streamClient.subscribe('session.status', (event) => {
        setConnection(event.payload.connection)
        announceConnection(
          event.payload.connection === 'degraded' ? 'reconnecting' : event.payload.connection === 'error' ? 'error' : event.payload.connection,
          uiLocale
        )

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
        previousConnectionRef.current = current
      }),
      streamClient.subscribe('transcript.partial', (event) => applyTranscriptPartial(event.payload)),
      streamClient.subscribe('transcript.final', (event) => {
        applyTranscriptFinal(event.payload)
        const currentMode = useLiveSessionStore.getState().selectedLanguage
        if (currentMode !== 'ja') {
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
      streamClient.subscribe('assist.term', (event) => appendAssistTerms(event.payload)),
      streamClient.subscribe('error', (event) => {
        showToast({
          variant: event.payload.recoverable ? 'warning' : 'danger',
          title: t('live.messages.liveEventErrorTitle'),
          message: event.payload.message,
        })
      }),
    ]

    streamClient.setTransport(sseStreamTransport)

    connectStream()

    return () => {
      subscriptions.forEach((unsubscribe) => unsubscribe())
      streamClient.disconnect()
    }
  }, [
    announceConnection,
    applyTranscriptFinal,
    applyTranscriptPartial,
    applyTranslationFinal,
    pushSourceFrame,
    pushSourceOcr,
    sessionId,
    appendAssistTerms,
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
    return () => {
      stopRecording()
      resetLiveData()
      setSessionId(null)
      autoStartedSessionIdRef.current = null
      previousSessionIdRef.current = null
      resumeRecordingOnVisibleRef.current = false
    }
  }, [resetLiveData, setSessionId, stopRecording])

  useEffect(() => {
    if (!lastError) {
      return
    }
    showToast({ variant: 'danger', title: t('live.messages.micErrorTitle'), message: lastError })
  }, [lastError, showToast, t])

  useEffect(() => {
    if (selectedLanguage !== 'ja') {
      return
    }
    setTranslationFallbackActive(false)
  }, [selectedLanguage, setTranslationFallbackActive])

  useEffect(() => {
    if (selectedLanguage === 'ja') {
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
    notifyTranslationFallback,
    selectedLanguage,
    setTranslationFallbackActive,
    transformSubtitleForMode,
  ])

  const CONNECTION_LABELS: Record<string, string> = {
    connecting: t('live.connection.connecting'),
    live: t('live.connection.live'),
    reconnecting: t('live.connection.reconnecting'),
    degraded: t('live.connection.degraded'),
    error: t('live.connection.error'),
  }

  const CONNECTION_BADGE: Record<string, string> = {
    connecting: 'badge-warning',
    live: 'badge-live',
    reconnecting: 'badge-warning',
    degraded: 'badge-warning',
    error: 'badge-danger',
  }

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
              className={`badge ${CONNECTION_BADGE[connection] ?? 'badge-muted'}`}
              title={t('live.aria.sessionIdTitle', { sessionId })}
            >
              {CONNECTION_LABELS[connection] ?? connection}
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
              className={`btn w-full sm:w-auto ${isRecording ? 'btn-secondary' : 'btn-primary'}`}
              onClick={() => (isRecording ? stopRecording() : startRecording())}
            >
              {isRecording ? t('live.stream.stopRecording') : t('live.stream.startRecording')}
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
