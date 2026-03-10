import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/pages/landing/LandingPage', () => ({
  LandingPage: () => <div>Landing Page</div>,
}))

vi.mock('@/pages/lectures/LecturesPage', () => ({
  LecturesPage: () => <div>Lectures Page</div>,
}))

vi.mock('@/pages/lectures/LectureLivePage', () => ({
  LectureLivePage: () => <div>Lecture Live Page</div>,
}))

vi.mock('@/pages/settings/SettingsPage', () => ({
  SettingsPage: () => <div>Settings Page</div>,
}))

describe('AppRouter', () => {
  it('redirects legacy sources route to lectures', async () => {
    window.history.pushState({}, '', '/lectures/session-123/sources')

    const { AppRouter } = await import('./router')
    render(<AppRouter />)

    await waitFor(() => {
      expect(screen.getByText('Lectures Page')).toBeInTheDocument()
    })
  })
})
