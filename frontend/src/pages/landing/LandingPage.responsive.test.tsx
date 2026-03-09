import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { LandingPage } from './LandingPage'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      language: 'ja',
      resolvedLanguage: 'ja',
      getFixedT: () => (key: string) => key,
    },
  }),
}))

vi.mock('@/hooks/useUiLanguagePreference', () => ({
  useUiLanguagePreference: () => ({
    language: 'ja',
    setLanguage: vi.fn(),
    isPersisting: false,
  }),
}))

describe('LandingPage responsive layout', () => {
  it('renders core mobile actions at 360px width', () => {
    window.resizeTo(360, 800)

    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('heading', { name: 'landing.title' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'landing.demo' })).toBeInTheDocument()
  })
})
