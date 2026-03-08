import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMicrophoneInput } from './useMicrophoneInput'
import { useAudioInputStore } from '@/stores/audioInputStore'

type MockTrack = {
  stop: ReturnType<typeof vi.fn>
}

type MockStream = {
  getTracks: () => MockTrack[]
}

function Probe() {
  const { startRecording, stopRecording } = useMicrophoneInput()
  const isRecording = useAudioInputStore((state) => state.isRecording)
  const micPermission = useAudioInputStore((state) => state.micPermission)
  const lastError = useAudioInputStore((state) => state.lastError)

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          void startRecording()
        }}
      >
        start
      </button>
      <button type="button" onClick={stopRecording}>
        stop
      </button>
      <div data-testid="recording">{String(isRecording)}</div>
      <div data-testid="permission">{micPermission}</div>
      <div data-testid="error">{lastError ?? ''}</div>
    </div>
  )
}

describe('useMicrophoneInput', () => {
  const originalMediaRecorder = globalThis.MediaRecorder
  const originalAudioContext = globalThis.AudioContext
  const originalNavigator = globalThis.navigator

  beforeEach(() => {
    useAudioInputStore.getState().reset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    globalThis.MediaRecorder = originalMediaRecorder
    globalThis.AudioContext = originalAudioContext
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: originalNavigator,
    })
  })

  it('starts recording even when MediaRecorder and AudioContext are unavailable', async () => {
    const tracks: MockTrack[] = [{ stop: vi.fn() }]
    const stream: MockStream = {
      getTracks: () => tracks,
    }

    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: {
        mediaDevices: {
          getUserMedia: vi.fn(async () => stream),
        },
      },
    })

    globalThis.MediaRecorder = undefined as unknown as typeof MediaRecorder
    globalThis.AudioContext = undefined as unknown as typeof AudioContext

    const user = userEvent.setup()
    render(<Probe />)

    await user.click(screen.getByRole('button', { name: 'start' }))

    await waitFor(() => {
      expect(screen.getByTestId('recording')).toHaveTextContent('true')
      expect(screen.getByTestId('permission')).toHaveTextContent('granted')
      expect(screen.getByTestId('error')).toHaveTextContent('')
    })
  })

  it('shows a permission error only when getUserMedia is actually denied', async () => {
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: {
        mediaDevices: {
          getUserMedia: vi.fn(async () => {
            throw new DOMException('denied', 'NotAllowedError')
          }),
        },
      },
    })

    const user = userEvent.setup()
    render(<Probe />)

    await user.click(screen.getByRole('button', { name: 'start' }))

    await waitFor(() => {
      expect(screen.getByTestId('recording')).toHaveTextContent('false')
      expect(screen.getByTestId('permission')).toHaveTextContent('denied')
      expect(screen.getByTestId('error')).toHaveTextContent(
        'マイク利用が拒否されました。ブラウザ設定を確認してください。'
      )
    })
  })
})
