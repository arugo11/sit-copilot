import type { StreamTransport, WsEvent } from '../types'

export class WebSocketTransport implements StreamTransport {
  async connect(_sessionId: string): Promise<void> {
    // Skeleton only. Real WS integration will map incoming messages to WsEvent.
  }

  disconnect(): void {
    // Skeleton only.
  }

  send(_event: WsEvent): void {
    // Skeleton only.
  }

  onEvent(_handler: (event: WsEvent) => void): () => void {
    return () => {}
  }
}
