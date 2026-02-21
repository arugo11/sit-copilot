import { create } from 'zustand'

type MicPermission = 'unknown' | 'granted' | 'denied'

interface AudioInputStore {
  micPermission: MicPermission
  isRecording: boolean
  audioLevel: number
  lastError: string | null
  setMicPermission: (permission: MicPermission) => void
  setIsRecording: (isRecording: boolean) => void
  setAudioLevel: (audioLevel: number) => void
  setLastError: (error: string | null) => void
  reset: () => void
}

export const useAudioInputStore = create<AudioInputStore>((set) => ({
  micPermission: 'unknown',
  isRecording: false,
  audioLevel: 0,
  lastError: null,
  setMicPermission: (micPermission) => set({ micPermission }),
  setIsRecording: (isRecording) => set({ isRecording }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setLastError: (lastError) => set({ lastError }),
  reset: () =>
    set({
      micPermission: 'unknown',
      isRecording: false,
      audioLevel: 0,
      lastError: null,
    }),
}))
