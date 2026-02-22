/**
 * Lecture Live Page
 * SSE-first live stream
 */

import { useCallback, useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useConnectionAnnouncer } from '@/hooks/useLiveRegion'
import { useToast } from '@/components/common/Toast'
import { AppShell } from '@/components/common/AppShell'
import { SourcePanel } from '@/features/live/components/SourcePanel'
import { TranscriptPanel } from '@/features/live/components/TranscriptPanel'
import { AssistPanel } from '@/features/live/components/AssistPanel'
import { streamClient, sseStreamTransport } from '@/lib/stream'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useMicrophoneInput } from '@/features/audio/useMicrophoneInput'
import { useSpeechRecognition } from '@/features/audio/useSpeechRecognition'
import { useUserSettings } from '@/lib/api/hooks'
import { demoApi, getApiErrorMessage } from '@/lib/api/client'

const SUMMARY_TRIGGER_CHUNK_COUNT = 3
const ERROR_TOAST_THROTTLE_MS = 5000

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

export function LectureLivePage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const sessionId = id ?? 'demo-session'
  const { showToast } = useToast()
  const { announceConnection } = useConnectionAnnouncer()
  const { data: userSettings } = useUserSettings()

  const connection = useLiveSessionStore((state) => state.connection)
  const transcriptLagMs = useLiveSessionStore((state) => state.transcriptLagMs)
  const cameraEnabled = useLiveSessionStore((state) => state.cameraEnabled)
  const selectedLanguage = useLiveSessionStore((state) => state.selectedLanguage)
  const setConnection = useLiveSessionStore((state) => state.setConnection)
  const setCameraEnabled = useLiveSessionStore((state) => state.setCameraEnabled)
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
  const transcriptLines = useLiveSessionStore((state) => state.transcriptLines)
  const pushSourceFrame = useLiveSessionStore((state) => state.pushSourceFrame)
  const pushSourceOcr = useLiveSessionStore((state) => state.pushSourceOcr)
  const setAssistSummary = useLiveSessionStore((state) => state.setAssistSummary)
  const setAssistTerms = useLiveSessionStore((state) => state.setAssistTerms)
  const hydrateFromSettings = useLiveSessionStore((state) => state.hydrateFromSettings)
  const resetLiveData = useLiveSessionStore((state) => state.resetLiveData)
  const autoStartAttemptedRef = useRef(false)
  const chunkIndexRef = useRef(0)
  const previousConnectionRef = useRef(connection)
  const lastReconnectToastAtRef = useRef(0)
  const lastErrorToastAtRef = useRef(0)

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
          try {
            const transformed = await demoApi.transformSubtitle({
              session_id: sessionId,
              text: transcriptForAssist,
              target_lang_mode: currentMode,
            })
            const translated = sanitizeTranslatedText(
              transformed.transformed_text || transcriptForAssist,
              currentMode
            )
            applyTranslationFinal(ingested.event_id, translated, currentMode)
          } catch (translationError) {
            console.warn('[subtitle-translation] post-correction transform failed', {
              sessionId,
              eventId: ingested.event_id,
              error: translationError,
            })
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
            if (keytermsResult.key_terms.length > 0) {
              setAssistTerms(
                keytermsResult.key_terms.map((term) => ({
                  term: term.term,
                  explanation: term.explanation || '',
                  translation: term.translation || term.term,
                }))
              )
            }
          } catch (keytermsError) {
            // 専門用語分析が失敗しても、字幕自体は正常に処理されたのでエラーは無視
            console.warn('Key terms analysis failed:', keytermsError)
          }
        }

        // 3回ごとに要約を更新（トグルONの場合のみ）
        chunkIndexRef.current += 1
        if (
          useLiveSessionStore.getState().summaryEnabled &&
          chunkIndexRef.current % SUMMARY_TRIGGER_CHUNK_COUNT === 0
        ) {
          await demoApi.getLatestSummary(sessionId)
        }
      } catch (error) {
        const nowMs = Date.now()
        if (nowMs - lastErrorToastAtRef.current < ERROR_TOAST_THROTTLE_MS) {
          return
        }
        lastErrorToastAtRef.current = nowMs
        showToast({
          variant: 'danger',
          title: '音声同期エラー',
          message: getApiErrorMessage(error, '音声チャンクの送信に失敗しました。'),
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
      setAssistTerms,
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

  const transformSubtitleForMode = useCallback(
    async (text: string, mode: 'ja' | 'easy-ja' | 'en'): Promise<string> => {
      if (mode === 'ja') {
        return text
      }

      try {
        const transformed = await demoApi.transformSubtitle({
          session_id: sessionId,
          text,
          target_lang_mode: mode,
        })
        return sanitizeTranslatedText(transformed.transformed_text || text, mode)
      } catch {
        return text
      }
    },
    [sessionId]
  )

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
    hydrateFromSettings({
      language: userSettings?.language,
      transcriptDensity: userSettings?.transcriptDensity,
      autoScrollDefault: userSettings?.autoScrollDefault,
    })
  }, [hydrateFromSettings, userSettings])

  useEffect(() => {
    if (autoStartAttemptedRef.current || isRecording) {
      return
    }
    autoStartAttemptedRef.current = true
    setSessionId(sessionId)
    void startRecording()
  }, [isRecording, startRecording, sessionId, setSessionId])

  useEffect(() => {
    const subscriptions = [
      streamClient.subscribe('session.status', (event) => {
        setConnection(event.payload.connection)
        announceConnection(
          event.payload.connection === 'degraded' ? 'reconnecting' : event.payload.connection === 'error' ? 'error' : event.payload.connection,
          'ja'
        )

        const previous = previousConnectionRef.current
        const current = event.payload.connection
        if ((previous === 'reconnecting' || previous === 'error') && current === 'live') {
          showToast({
            variant: 'success',
            title: '接続復帰',
            message: 'ライブストリームに再接続しました。',
          })
        } else if (current === 'reconnecting') {
          const now = Date.now()
          if (now - lastReconnectToastAtRef.current >= ERROR_TOAST_THROTTLE_MS) {
            lastReconnectToastAtRef.current = now
            showToast({
              variant: 'warning',
              title: '再接続中',
              message: 'ライブストリームの再接続を試行しています。',
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
          void (async () => {
            const translated = await transformSubtitleForMode(
              event.payload.sourceLangText,
              currentMode
            )
            applyTranslationFinal(event.payload.id, translated, currentMode)
          })()
        }
      }),
      // 翻訳は /subtitle/transform の結果を正として扱う。
      // 旧経路の translation.final が届いても字幕を上書きしない。
      streamClient.subscribe('source.frame', (event) => pushSourceFrame(event.payload)),
      streamClient.subscribe('source.ocr', (event) => pushSourceOcr(event.payload)),
      streamClient.subscribe('assist.summary', (event) => setAssistSummary(event.payload)),
      streamClient.subscribe('assist.term', (event) => setAssistTerms(event.payload)),
      streamClient.subscribe('error', (event) => {
        showToast({
          variant: event.payload.recoverable ? 'warning' : 'danger',
          title: 'ライブイベントエラー',
          message: event.payload.message,
        })
      }),
    ]

    chunkIndexRef.current = 0
    streamClient.setTransport(sseStreamTransport)

    streamClient.connect(sessionId).catch((error) => {
      showToast({
        variant: 'warning',
        title: 'SSE接続失敗',
        message: `${getApiErrorMessage(error, 'ライブストリームを開始できませんでした。')} 自動再接続を継続します。`,
      })
    })

    return () => {
      subscriptions.forEach((unsubscribe) => unsubscribe())
      streamClient.disconnect()
      stopRecording()
      resetLiveData()
      setSessionId(null)
    }
  }, [
    announceConnection,
    applyTranscriptFinal,
    applyTranscriptPartial,
    applyTranslationFinal,
    pushSourceFrame,
    pushSourceOcr,
    resetLiveData,
    sessionId,
    setAssistSummary,
    setAssistTerms,
    setConnection,
    setSessionId,
    showToast,
    stopRecording,
  ])

  useEffect(() => {
    if (!lastError) {
      return
    }
    showToast({ variant: 'danger', title: 'マイクエラー', message: lastError })
  }, [lastError, showToast])

  useEffect(() => {
    if (selectedLanguage === 'ja' || transcriptLines.length === 0) {
      return
    }

    transcriptLines.forEach((line) => {
      if (line.translatedLangMode === selectedLanguage) {
        return
      }
      void (async () => {
        const translated = await transformSubtitleForMode(
          line.sourceLangText,
          selectedLanguage
        )
        applyTranslationFinal(line.id, translated, selectedLanguage)
      })()
    })
  }, [
    applyTranslationFinal,
    selectedLanguage,
    transcriptLines,
    transformSubtitleForMode,
  ])

  const CONNECTION_LABELS: Record<string, string> = {
    connecting: '接続中',
    live: '接続中',
    reconnecting: '再接続中',
    degraded: '低品質',
    error: 'エラー',
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

  return (
    <AppShell
      topbar={
        <div className="py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold">{t('live.stream.title')}</h1>
            <span
              className={`badge ${CONNECTION_BADGE[connection] ?? 'badge-muted'}`}
              title={`Session: ${sessionId}`}
            >
              {CONNECTION_LABELS[connection] ?? connection}
            </span>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-fg-secondary hover:text-fg-primary transition-colors"
              title={sessionId}
              onClick={() => navigator.clipboard.writeText(sessionId)}
              aria-label="セッション ID をコピー"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {shortSessionId}
            </button>
            {transcriptLagMs > 300 && (
              <span className="text-xs text-warning" title="字幕遅延">⚠️ {transcriptLagMs}ms</span>
            )}
          </div>
          <div className="flex gap-2 items-center">
            <button
              type="button"
              className={`btn ${isRecording ? 'btn-secondary' : 'btn-primary'}`}
              onClick={() => (isRecording ? stopRecording() : startRecording())}
            >
              {isRecording ? t('live.stream.stopRecording') : t('live.stream.startRecording')}
            </button>
            <button
              type="button"
              className={`btn ${cameraEnabled ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setCameraEnabled(!cameraEnabled)}
              aria-pressed={cameraEnabled}
            >
              {cameraEnabled ? t('live.stream.cameraOn') : t('live.stream.cameraOff')}
            </button>
            {/* Audio level bars */}
            <div className="flex items-end gap-0.5 h-5" aria-label={`入力レベル ${Math.round(audioLevel * 100)}%`} title={`入力 ${Math.round(audioLevel * 100)}%`}>
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
            <Link to={`/lectures/${sessionId}/review`} className="btn btn-secondary">
              {t('live.stream.toReview')}
            </Link>
          </div>
        </div>
      }
      sidebar={cameraEnabled ? <SourcePanel /> : undefined}
      rightRail={<AssistPanel onAskMiniQuestion={(q) => showToast({ variant: 'info', title: 'ミニ回答', message: `${q} → 詳細回答はreview画面で確認してください。` })} />}
    >
      <div className="h-[calc(100vh-130px)]">
        <TranscriptPanel />
      </div>
    </AppShell>
  )
}
