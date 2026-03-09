import { useCallback, useEffect, useRef } from 'react'
import { useAudioInputStore } from '@/stores/audioInputStore'

interface MicrophoneOptions {
  onChunk?: (chunk: Blob) => void
}

type AudioContextCtor = typeof AudioContext
type WindowWithWebkitAudioContext = Window & {
  webkitAudioContext?: AudioContextCtor
}

function resolveAudioContextCtor(): AudioContextCtor | null {
  if (typeof window === 'undefined') {
    return null
  }

  const candidate =
    window.AudioContext ??
    (window as WindowWithWebkitAudioContext).webkitAudioContext
  return candidate ?? null
}

function resolveMicrophoneStartError(error: unknown): {
  permission: 'unknown' | 'denied'
  message: string
} {
  const errorName =
    error instanceof DOMException
      ? error.name
      : typeof error === 'object' &&
          error !== null &&
          'name' in error &&
          typeof error.name === 'string'
        ? error.name
        : ''

  if (
    errorName === 'NotAllowedError' ||
    errorName === 'PermissionDeniedError' ||
    errorName === 'SecurityError'
  ) {
    return {
      permission: 'denied',
      message: 'マイク利用が拒否されました。ブラウザ設定を確認してください。',
    }
  }

  if (errorName === 'NotFoundError' || errorName === 'DevicesNotFoundError') {
    return {
      permission: 'unknown',
      message: '利用できるマイクが見つかりません。',
    }
  }

  if (errorName === 'NotReadableError' || errorName === 'TrackStartError') {
    return {
      permission: 'unknown',
      message: 'マイクを使用できません。他のアプリが使用中の可能性があります。',
    }
  }

  if (errorName === 'OverconstrainedError' || errorName === 'ConstraintNotSatisfiedError') {
    return {
      permission: 'unknown',
      message: 'このブラウザでは要求したマイク設定を利用できません。',
    }
  }

  return {
    permission: 'unknown',
    message: 'マイクの開始に失敗しました。ブラウザを再読み込みしてもう一度お試しください。',
  }
}

export function useMicrophoneInput(options: MicrophoneOptions = {}) {
  const { onChunk } = options

  const {
    isRecording,
    micPermission,
    audioLevel,
    lastError,
    setMicPermission,
    setIsRecording,
    setAudioLevel,
    setLastError,
  } = useAudioInputStore()

  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafIdRef = useRef<number | null>(null)
  const onChunkRef = useRef<MicrophoneOptions['onChunk']>(onChunk)

  useEffect(() => {
    onChunkRef.current = onChunk
  }, [onChunk])

  const stopLevelMonitor = useCallback(() => {
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
    }
    setAudioLevel(0)
  }, [setAudioLevel])

  const startLevelMonitor = useCallback(() => {
    const analyser = analyserRef.current
    if (!analyser) {
      return
    }

    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    const loop = () => {
      analyser.getByteTimeDomainData(dataArray)
      let sum = 0
      for (let i = 0; i < dataArray.length; i += 1) {
        const normalized = (dataArray[i] - 128) / 128
        sum += normalized * normalized
      }
      const rms = Math.sqrt(sum / dataArray.length)
      setAudioLevel(Math.min(1, rms * 2.8))
      rafIdRef.current = requestAnimationFrame(loop)
    }

    rafIdRef.current = requestAnimationFrame(loop)
  }, [setAudioLevel])

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try {
        recorderRef.current.stop()
      } catch (error) {
        console.warn('[microphone] failed to stop MediaRecorder cleanly', error)
      }
    }
    recorderRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    audioContextRef.current?.close()
    audioContextRef.current = null
    analyserRef.current = null
    stopLevelMonitor()
    setIsRecording(false)
  }, [setIsRecording, stopLevelMonitor])

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission('unknown')
      setLastError('このブラウザはマイク入力をサポートしていません。')
      setIsRecording(false)
      return
    }

    try {
      setLastError(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      setMicPermission('granted')
      streamRef.current = stream
      setIsRecording(true)

      if (typeof MediaRecorder !== 'undefined') {
        try {
          const recorder = new MediaRecorder(stream)
          recorderRef.current = recorder

          recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
              onChunkRef.current?.(event.data)
            }
          }

          recorder.onerror = () => {
            setLastError('マイク録音中にエラーが発生しました。')
          }

          recorder.start(1000)
        } catch (error) {
          console.warn('[microphone] MediaRecorder unavailable; continuing without chunks', error)
          recorderRef.current = null
        }
      }

      const AudioContextClass = resolveAudioContextCtor()
      if (AudioContextClass) {
        try {
          const audioContext = new AudioContextClass()
          audioContextRef.current = audioContext
          const sourceNode = audioContext.createMediaStreamSource(stream)
          const analyserNode = audioContext.createAnalyser()
          analyserNode.fftSize = 512
          sourceNode.connect(analyserNode)
          analyserRef.current = analyserNode
          startLevelMonitor()
        } catch (error) {
          console.warn('[microphone] AudioContext unavailable; continuing without level meter', error)
          audioContextRef.current = null
          analyserRef.current = null
        }
      }

    } catch (error) {
      const resolved = resolveMicrophoneStartError(error)
      setMicPermission(resolved.permission)
      setLastError(resolved.message)
      setIsRecording(false)
    }
  }, [setIsRecording, setLastError, setMicPermission, startLevelMonitor])

  useEffect(() => {
    return () => {
      stopRecording()
    }
  }, [stopRecording])

  return {
    isRecording,
    micPermission,
    audioLevel,
    lastError,
    startRecording,
    stopRecording,
  }
}
