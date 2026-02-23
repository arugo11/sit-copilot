import type { StreamTransport, WsEvent } from '../types'

const SAMPLE_TEXT = [
  {
    speaker: '先生',
    ja: 'これは講義字幕サンプルです（リアルタイム字幕1）。',
    en: 'This is lecture subtitle sample text (realtime subtitle 1).',
  },
  {
    speaker: '先生',
    ja: 'これは講義字幕サンプルです（リアルタイム字幕2）。',
    en: 'This is lecture subtitle sample text (realtime subtitle 2).',
  },
  {
    speaker: '先生',
    ja: 'これは講義字幕サンプルです（リアルタイム字幕3）。',
    en: 'This is lecture subtitle sample text (realtime subtitle 3).',
  },
]

export class MockStreamTransport implements StreamTransport {
  private handler: ((event: WsEvent) => void) | null = null
  private connected = false
  private tickTimer: ReturnType<typeof setInterval> | null = null
  private currentMs = 0
  private textIndex = 0

  async connect(_sessionId: string): Promise<void> {
    this.connected = true
    this.emit({ type: 'session.status', payload: { connection: 'connecting' } })

    setTimeout(() => {
      if (!this.connected) return
      this.emit({ type: 'session.status', payload: { connection: 'live' } })
    }, 300)

    this.startTicking()
  }

  disconnect(): void {
    this.connected = false
    if (this.tickTimer) {
      clearInterval(this.tickTimer)
      this.tickTimer = null
    }
  }

  send(event: WsEvent): void {
    if (!this.connected) {
      return
    }
    this.emit(event)
  }

  onEvent(handler: (event: WsEvent) => void): () => void {
    this.handler = handler
    return () => {
      this.handler = null
    }
  }

  startQaStream(question: string): string {
    const answerId = `qa_${Date.now()}`
    const chunks = [
      `質問「${question}」への回答です。`,
      'これはQAストリームのサンプル回答1です。',
      'これはQAストリームのサンプル回答2です。',
    ]

    let chunkIndex = 0
    const timer = setInterval(() => {
      if (!this.connected) {
        clearInterval(timer)
        return
      }

      if (chunkIndex >= chunks.length) {
        clearInterval(timer)
        this.emit({
          type: 'qa.answer.done',
          payload: {
            answerId,
            followups: ['関連質問の候補1', '関連質問の候補2'],
          },
        })
        return
      }

      const textChunk = `${chunks[chunkIndex]}\n\n`
      this.emit({
        type: 'qa.answer.chunk',
        payload: {
          answerId,
          textChunk,
          citations: [
            {
              citationId: `c_${answerId}_${chunkIndex}`,
              type: 'audio',
              label: `発言 ${10 + chunkIndex}:0${chunkIndex}`,
              tsStartMs: this.currentMs,
              tsEndMs: this.currentMs + 4500,
            },
          ],
        },
      })
      chunkIndex += 1
    }, 700)

    return answerId
  }

  acceptAudioChunk(_chunk: Blob): void {
    if (!this.connected) {
      return
    }
    this.emit({ type: 'assist.summary', payload: { timestampMs: this.currentMs, points: ['音声チャンクを受信しました。'] } })
  }

  private startTicking(): void {
    if (this.tickTimer) {
      clearInterval(this.tickTimer)
    }

    this.tickTimer = setInterval(() => {
      if (!this.connected) {
        return
      }

      const sample = SAMPLE_TEXT[this.textIndex % SAMPLE_TEXT.length]
      const lineId = `line_${this.currentMs}`
      const startMs = this.currentMs
      const endMs = this.currentMs + 4500

      this.emit({
        type: 'transcript.partial',
        payload: {
          id: lineId,
          tsStartMs: startMs,
          tsEndMs: endMs,
          speakerLabel: sample.speaker,
          sourceLangText: sample.ja.slice(0, Math.floor(sample.ja.length * 0.6)),
          isPartial: true,
          confidence: 0.72,
          sourceRefs: { audioSegmentId: `audio_${lineId}` },
        },
      })

      setTimeout(() => {
        if (!this.connected) return
        this.emit({
          type: 'transcript.final',
          payload: {
            id: lineId,
            tsStartMs: startMs,
            tsEndMs: endMs,
            speakerLabel: sample.speaker,
            sourceLangText: sample.ja,
            isPartial: false,
            confidence: 0.94,
            sourceRefs: {
              audioSegmentId: `audio_${lineId}`,
              sourceFrameIds: [`frame_slide_${lineId}`, `frame_board_${lineId}`],
            },
          },
        })

        this.emit({
          type: 'translation.final',
          payload: {
            lineId,
            translatedText: sample.en,
          },
        })
      }, 450)

      this.emit({
        type: 'source.frame',
        payload: {
          id: `frame_slide_${lineId}`,
          source: 'slide',
          timestampMs: this.currentMs,
          thumbnailUrl: 'https://dummyimage.com/640x360/e2e8f0/0f172a&text=Slide+Frame',
          ocrExcerpt: 'Overfitting and regularization',
        },
      })

      this.emit({
        type: 'source.frame',
        payload: {
          id: `frame_board_${lineId}`,
          source: 'board',
          timestampMs: this.currentMs,
          thumbnailUrl: 'https://dummyimage.com/640x360/cbd5e1/0f172a&text=Board+Frame',
          ocrExcerpt: 'L2 + Validation loss',
        },
      })

      this.emit({
        type: 'source.ocr',
        payload: {
          frameId: `frame_board_${lineId}`,
          source: 'board',
          timestampMs: this.currentMs,
          text: 'これはOCRイベントのサンプルです',
        },
      })

      this.emit({
        type: 'assist.summary',
        payload: {
          timestampMs: this.currentMs,
          points: [
            '講義要約サンプルのポイント1',
            '講義要約サンプルのポイント2',
          ],
        },
      })

      this.emit({
        type: 'assist.term',
        payload: [
          { term: '用語1', explanation: '講義中のサンプル説明です', translation: 'Term 1' },
          { term: '用語2', explanation: '講義中のサンプル説明です', translation: 'Term 2' },
        ],
      })

      this.currentMs += 5000
      this.textIndex += 1
    }, 2400)
  }

  private emit(event: WsEvent): void {
    this.handler?.(event)
  }
}
