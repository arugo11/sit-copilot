import type { StreamTransport, WsEvent } from './types'

const RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10000] as const

type EventType = WsEvent['type']
type Handler<T extends EventType> = (event: Extract<WsEvent, { type: T }>) => void

export class StreamClient {
  private transport: StreamTransport
  private sessionId: string | null = null
  private unsubscribeTransport: (() => void) | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempt = 0
  private shouldReconnect = false
  private isConnecting = false
  private handlers: Map<EventType, Set<(event: WsEvent) => void>> = new Map()

  constructor(transport: StreamTransport) {
    this.transport = transport
  }

  setTransport(transport: StreamTransport): void {
    this.disconnect()
    this.transport = transport
  }

  async connect(sessionId: string): Promise<void> {
    this.sessionId = sessionId
    this.shouldReconnect = true
    this.clearReconnectTimer()
    await this.connectWithTransport()
  }

  disconnect(): void {
    this.shouldReconnect = false
    this.clearReconnectTimer()
    this.reconnectAttempt = 0
    if (this.unsubscribeTransport) {
      this.unsubscribeTransport()
      this.unsubscribeTransport = null
    }
    this.transport.disconnect()
  }

  send(event: WsEvent): void {
    this.transport.send(event)
  }

  subscribe<T extends EventType>(
    type: T,
    handler: Handler<T>
  ): () => void {
    const wrapped = handler as unknown as (event: WsEvent) => void
    const current = this.handlers.get(type) ?? new Set<(event: WsEvent) => void>()
    current.add(wrapped)
    this.handlers.set(type, current)

    return () => {
      const target = this.handlers.get(type)
      if (!target) return
      target.delete(wrapped)
      if (target.size === 0) {
        this.handlers.delete(type)
      }
    }
  }

  private async connectWithTransport(): Promise<void> {
    if (!this.sessionId || this.isConnecting) {
      return
    }

    this.isConnecting = true
    this.unsubscribeTransport?.()
    this.transport.disconnect()
    this.unsubscribeTransport = this.transport.onEvent((event) => {
      if (event.type === 'session.status') {
        if (event.payload.connection === 'live') {
          this.reconnectAttempt = 0
          this.clearReconnectTimer()
        } else if (
          event.payload.connection === 'reconnecting' ||
          event.payload.connection === 'error'
        ) {
          this.scheduleReconnect()
        }
      }
      if (event.type === 'error' && event.payload.recoverable) {
        this.scheduleReconnect()
      }
      this.emit(event)
    })

    try {
      await this.transport.connect(this.sessionId)
      this.reconnectAttempt = 0
    } catch {
      this.emit({ type: 'session.status', payload: { connection: 'reconnecting' } })
      this.scheduleReconnect()
    } finally {
      this.isConnecting = false
    }
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect || !this.sessionId || this.reconnectTimer) {
      return
    }

    const index = Math.min(this.reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)
    const delay = RECONNECT_DELAYS_MS[index]
    this.reconnectAttempt += 1

    this.clearReconnectTimer()
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      void this.connectWithTransport()
    }, delay)
  }

  private clearReconnectTimer(): void {
    if (!this.reconnectTimer) {
      return
    }
    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  private emit(event: WsEvent): void {
    const scopedHandlers = this.handlers.get(event.type)
    if (!scopedHandlers) {
      return
    }
    scopedHandlers.forEach((handler) => handler(event))
  }
}
