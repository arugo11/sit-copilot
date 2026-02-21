import { StreamClient } from './StreamClient'
import { MockStreamTransport } from './transports/MockStreamTransport'
import { SseTransport } from './transports/SseTransport'

export const sseStreamTransport = new SseTransport()
export const mockStreamTransport = new MockStreamTransport()
export const streamClient = new StreamClient(sseStreamTransport)

export * from './types'
