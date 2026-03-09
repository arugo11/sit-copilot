import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LectureSourcesPage } from './LectureSourcesPage'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      language: 'ja',
      resolvedLanguage: 'ja',
    },
  }),
}))

vi.mock('@/hooks', () => ({
  useIsMobile: () => true,
}))

describe('LectureSourcesPage responsive layout', () => {
  it('switches to card layout on mobile', () => {
    render(<LectureSourcesPage />)

    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0)
  })
})
