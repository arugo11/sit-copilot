/**
 * Lecture Live Page
 * SSE-first live stream with mock fallback
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
import { streamClient, mockStreamTransport, sseStreamTransport } from '@/lib/stream'
import { useLiveSessionStore } from '@/stores/liveSessionStore'
import { useMicrophoneInput } from '@/features/audio/useMicrophoneInput'
import { useUserSettings } from '@/lib/api/hooks'
import { demoApi, getApiErrorMessage } from '@/lib/api/client'

const CHUNK_WINDOW_MS = 4000
const SUMMARY_TRIGGER_CHUNK_COUNT = 3
const ERROR_TOAST_THROTTLE_MS = 5000
const DEMO_TRANSCRIPT_SNIPPETS = [
  '今日は機械学習の過学習について説明します。',
  '訓練データでは高精度でも未知データで性能が落ちる状態です。',
  '対策として正則化と検証データ監視が重要です。',
]

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
  const setConnection = useLiveSessionStore((state) => state.setConnection)
  const setCameraEnabled = useLiveSessionStore((state) => state.setCameraEnabled)
  const applyTranscriptPartial = useLiveSessionStore((state) => state.applyTranscriptPartial)
  const applyTranscriptFinal = useLiveSessionStore((state) => state.applyTranscriptFinal)
  const applyTranslationFinal = useLiveSessionStore((state) => state.applyTranslationFinal)
  const pushSourceFrame = useLiveSessionStore((state) => state.pushSourceFrame)
  const pushSourceOcr = useLiveSessionStore((state) => state.pushSourceOcr)
  const setAssistSummary = useLiveSessionStore((state) => state.setAssistSummary)
  const setAssistTerms = useLiveSessionStore((state) => state.setAssistTerms)
  const hydrateFromSettings = useLiveSessionStore((state) => state.hydrateFromSettings)
  const resetLiveData = useLiveSessionStore((state) => state.resetLiveData)
  const autoStartAttemptedRef = useRef(false)
  const usingMockTransportRef = useRef(false)
  const chunkIndexRef = useRef(0)
  const previousConnectionRef = useRef(connection)
  const lastReconnectToastAtRef = useRef(0)
  const lastErrorToastAtRef = useRef(0)

  const handleAudioChunk = useCallback((chunk: Blob) => {
    if (usingMockTransportRef.current) {
      mockStreamTransport.acceptAudioChunk(chunk)
      return
    }

    const chunkIndex = chunkIndexRef.current
    chunkIndexRef.current += 1

    const startMs = chunkIndex * CHUNK_WINDOW_MS
    const endMs = startMs + CHUNK_WINDOW_MS
    const sampleText = DEMO_TRANSCRIPT_SNIPPETS[chunkIndex % DEMO_TRANSCRIPT_SNIPPETS.length]
    const transcriptText = `${sampleText} (audio:${chunk.size}bytes)`

    void demoApi
      .ingestSpeechChunk({
        session_id: sessionId,
        start_ms: startMs,
        end_ms: endMs,
        text: transcriptText,
        confidence: 0.9,
        is_final: true,
        speaker: 'teacher',
      })
      .then(async () => {
        if ((chunkIndex + 1) % SUMMARY_TRIGGER_CHUNK_COUNT === 0) {
          await demoApi.getLatestSummary(sessionId)
        }
      })
      .catch((error) => {
        const now = Date.now()
        if (now - lastErrorToastAtRef.current < ERROR_TOAST_THROTTLE_MS) {
          return
        }
        lastErrorToastAtRef.current = now
        showToast({
          variant: 'danger',
          title: '音声同期エラー',
          message: getApiErrorMessage(error, '音声チャンクの送信に失敗しました。'),
        })
      })
  }, [sessionId, showToast])

  const { isRecording, audioLevel, lastError, startRecording, stopRecording } =
    useMicrophoneInput({
      onChunk: handleAudioChunk,
    })

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
    void startRecording()
  }, [isRecording, startRecording])

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
      streamClient.subscribe('transcript.final', (event) => applyTranscriptFinal(event.payload)),
      streamClient.subscribe('translation.final', (event) => applyTranslationFinal(event.payload.lineId, event.payload.translatedText)),
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
    usingMockTransportRef.current = false
    streamClient.setTransport(sseStreamTransport)

    streamClient.connect(sessionId).catch((error) => {
      usingMockTransportRef.current = true
      streamClient.setTransport(mockStreamTransport)
      void streamClient.connect(sessionId)

      showToast({
        variant: 'warning',
        title: 'SSE接続失敗',
        message: `${getApiErrorMessage(error, 'ライブストリームを開始できませんでした。')} Mockモードへ切り替えます。`,
      })
    })

    return () => {
      subscriptions.forEach((unsubscribe) => unsubscribe())
      streamClient.disconnect()
      stopRecording()
      resetLiveData()
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
    showToast,
    stopRecording,
  ])

  useEffect(() => {
    if (!lastError) {
      return
    }
    showToast({ variant: 'danger', title: 'マイクエラー', message: lastError })
  }, [lastError, showToast])

  return (
    <AppShell
      topbar={
        <div className="py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold">{t('live.stream.title')}: {sessionId}</h1>
            <span className={`badge ${connection === 'live' ? 'badge-success' : connection === 'error' ? 'badge-danger' : 'badge-warning'}`}>
              {connection}
            </span>
            <span className="text-sm text-fg-secondary">字幕 {transcriptLagMs}ms</span>
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
              {t('live.stream.cameraInput')}: {cameraEnabled ? t('live.stream.cameraOn') : t('live.stream.cameraOff')}
            </button>
            <div className="text-xs text-fg-secondary min-w-20">入力 {Math.round(audioLevel * 100)}%</div>
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
