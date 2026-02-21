import { useCallback, useEffect, useRef } from 'react'
import { useAudioInputStore } from '@/stores/audioInputStore'

interface MicrophoneOptions {
  onChunk?: (chunk: Blob) => void
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
    recorderRef.current?.stop()
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
    try {
      setLastError(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      setMicPermission('granted')
      streamRef.current = stream

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

      const audioContext = new AudioContext()
      audioContextRef.current = audioContext
      const sourceNode = audioContext.createMediaStreamSource(stream)
      const analyserNode = audioContext.createAnalyser()
      analyserNode.fftSize = 512
      sourceNode.connect(analyserNode)
      analyserRef.current = analyserNode

      recorder.start(1000)
      setIsRecording(true)
      startLevelMonitor()
    } catch {
      setMicPermission('denied')
      setLastError('マイク利用が拒否されました。ブラウザ設定を確認してください。')
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
