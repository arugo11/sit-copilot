import type { StreamTransport, WsEvent } from '../types'

const SAMPLE_TEXT = [
  {
    speaker: '先生',
    ja: '今日は機械学習の過学習について説明します。',
    en: 'Today we will explain overfitting in machine learning.',
  },
  {
    speaker: '先生',
    ja: '訓練データでは高精度でも未知データで性能が落ちる状態です。',
    en: 'It means high accuracy on training data but poor performance on unseen data.',
  },
  {
    speaker: '先生',
    ja: '対策として正則化と検証データの監視が重要です。',
    en: 'Regularization and validation monitoring are key countermeasures.',
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
      '過学習は学習データに適合しすぎて汎化性能が下がる状態を指します。',
      '講義では正則化と検証データ監視が対策として説明されました。',
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
            followups: ['正則化の具体例は？', '検証データはどう分割する？'],
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
          text: '正則化 (L2) + 検証データで過学習を検知',
        },
      })

      this.emit({
        type: 'assist.summary',
        payload: {
          timestampMs: this.currentMs,
          points: [
            '過学習は未知データで性能が落ちる',
            '正則化と検証データ監視が対策',
          ],
        },
      })

      this.emit({
        type: 'assist.term',
        payload: [
          { term: '過学習', explanation: '学習データへ過度適合した状態', translation: 'Overfitting' },
          { term: '正則化', explanation: 'モデル複雑さを抑える手法', translation: 'Regularization' },
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
