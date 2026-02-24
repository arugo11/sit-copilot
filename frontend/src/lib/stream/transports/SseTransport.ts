import i18n from '@/lib/i18n'
import {
  API_BASE_URL,
  DEMO_USER_ID,
  LECTURE_API_TOKEN,
  getUnauthorizedMessage,
} from '@/lib/api/client'
import type { StreamTransport, WsEvent } from '../types'

const STREAM_ENDPOINT = '/api/v4/lecture/events/stream'

function localize(messageJa: string, messageEn: string): string {
  const language = i18n.resolvedLanguage ?? i18n.language
  return language.startsWith('en') ? messageEn : messageJa
}

function buildStreamUrl(sessionId: string): string {
  const resolvedBase = API_BASE_URL
    ? new URL(API_BASE_URL, window.location.origin)
    : new URL(window.location.origin)
  const url = new URL(STREAM_ENDPOINT, resolvedBase)
  url.searchParams.set('session_id', sessionId)
  return url.toString()
}

function parseWsEvent(raw: string): WsEvent | null {
  try {
    return JSON.parse(raw) as WsEvent
  } catch {
    return null
  }
}

export class SseTransport implements StreamTransport {
  private handler: ((event: WsEvent) => void) | null = null
  private controller: AbortController | null = null
  private disconnectRequested = false
  private buffer = ''

  async connect(sessionId: string): Promise<void> {
    this.disconnect()
    this.disconnectRequested = false
    this.buffer = ''

    this.emit({ type: 'session.status', payload: { connection: 'connecting' } })

    const controller = new AbortController()
    this.controller = controller

    const response = await fetch(buildStreamUrl(sessionId), {
      method: 'GET',
      headers: {
        'X-Lecture-Token': LECTURE_API_TOKEN,
        'X-User-Id': DEMO_USER_ID,
      },
      cache: 'no-store',
      signal: controller.signal,
    })

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error(getUnauthorizedMessage('lecture'))
      }
      throw new Error(`SSE connection failed (${response.status})`)
    }
    if (!response.body) {
      throw new Error('SSE response has no readable body')
    }

    this.emit({ type: 'session.status', payload: { connection: 'live' } })
    void this.consume(response.body.getReader())
  }

  disconnect(): void {
    this.disconnectRequested = true
    this.controller?.abort()
    this.controller = null
    this.buffer = ''
  }

  send(event: WsEvent): void {
    this.emit(event)
  }

  onEvent(handler: (event: WsEvent) => void): () => void {
    this.handler = handler
    return () => {
      this.handler = null
    }
  }

  private async consume(reader: ReadableStreamDefaultReader<Uint8Array>): Promise<void> {
    const decoder = new TextDecoder()

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }
        this.buffer += decoder.decode(value, { stream: true })
        this.flushBuffer()
      }

      this.buffer += decoder.decode()
      this.flushBuffer()
      if (!this.disconnectRequested) {
        this.emit({ type: 'session.status', payload: { connection: 'reconnecting' } })
      }
    } catch {
      if (!this.disconnectRequested) {
        this.emit({
          type: 'error',
          payload: {
            message: localize(
              'ライブストリーム接続が切断されました。',
              'Live stream connection was interrupted.'
            ),
            recoverable: true,
          },
        })
        this.emit({ type: 'session.status', payload: { connection: 'reconnecting' } })
      }
    }
  }

  private flushBuffer(): void {
    let separatorIndex = this.buffer.indexOf('\n\n')
    while (separatorIndex >= 0) {
      const rawEvent = this.buffer.slice(0, separatorIndex)
      this.buffer = this.buffer.slice(separatorIndex + 2)
      this.processRawEvent(rawEvent)
      separatorIndex = this.buffer.indexOf('\n\n')
    }
  }

  private processRawEvent(rawEvent: string): void {
    const lines = rawEvent
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0 && !line.startsWith(':'))

    if (lines.length === 0) {
      return
    }

    const dataLines = lines
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())

    if (dataLines.length === 0) {
      return
    }

    const parsed = parseWsEvent(dataLines.join('\n'))
    if (!parsed) {
      this.emit({
        type: 'error',
        payload: {
          message: localize(
            '受信イベントの解析に失敗しました。',
            'Failed to parse a received stream event.'
          ),
          recoverable: true,
        },
      })
      return
    }

    this.emit(parsed)
  }

  private emit(event: WsEvent): void {
    this.handler?.(event)
  }
}
