import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

describe('AppRouter', () => {
  it('shows the suspended notice on legacy routes', async () => {
    window.history.pushState({}, '', '/lectures/session-123/sources')

    const { AppRouter } = await import('./router')
    render(<AppRouter />)

    expect(screen.getByText('公開停止中')).toBeInTheDocument()
    expect(
      screen.getByText('現在このデモは公開を停止しています. 何かあれば me@argo11.devまで'),
    ).toBeInTheDocument()
  })
})
