import { useCallback, useEffect, useRef } from 'react'

interface SpeechRecognitionOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
  onResult?: (transcript: string, isFinal: boolean) => void
  onError?: (error: string) => void
}

export function useSpeechRecognition(options: SpeechRecognitionOptions = {}) {
  const {
    lang = 'ja-JP',
    continuous = true,
    interimResults = true,
    onResult,
    onError,
  } = options

  const recognitionRef = useRef<any>(null)
  const isListeningRef = useRef(false)

  const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition

  const startListening = useCallback(() => {
    if (!SpeechRecognitionAPI) {
      onError?.('このブラウザは音声認識をサポートしていません。')
      return
    }

    if (isListeningRef.current) {
      return
    }

    const recognition = new SpeechRecognitionAPI()
    recognitionRef.current = recognition

    recognition.lang = lang
    recognition.continuous = continuous
    recognition.interimResults = interimResults

    recognition.onresult = (event: any) => {
      const results = event.results
      for (let i = event.resultIndex; i < results.length; i++) {
        const result = results[i]
        const transcript = result[0].transcript
        onResult?.(transcript, result.isFinal)
      }
    }

    recognition.onerror = (event: any) => {
      const error = event.error as string
      onError?.(error)
      if (error === 'no-speech' || error === 'aborted') {
        isListeningRef.current = false
      }
    }

    recognition.onend = () => {
      if (isListeningRef.current) {
        // Restart if still supposed to be listening
        try {
          recognition.start()
        } catch {
          isListeningRef.current = false
        }
      }
    }

    try {
      recognition.start()
      isListeningRef.current = true
    } catch {
      onError?.('音声認識の開始に失敗しました。')
    }
  }, [SpeechRecognitionAPI, lang, continuous, interimResults, onResult, onError])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
    }
    isListeningRef.current = false
  }, [])

  useEffect(() => {
    return () => {
      stopListening()
    }
  }, [stopListening])

  return {
    isSupported: !!SpeechRecognitionAPI,
    startListening,
    stopListening,
  }
}
