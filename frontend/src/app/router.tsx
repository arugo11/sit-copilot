import { createBrowserRouter, RouterProvider } from 'react-router-dom'

const NOTICE_MESSAGE = '現在このデモは公開を停止しています. 何かあれば me@argo11.devまで'

function NoticePage() {
  return (
    <main className="notice-shell">
      <section className="notice-card" aria-labelledby="notice-title">
        <p className="notice-eyebrow">SIT Copilot</p>
        <h1 id="notice-title" className="notice-title">
          公開停止中
        </h1>
        <p className="notice-copy">{NOTICE_MESSAGE}</p>
      </section>
    </main>
  )
}

const router = createBrowserRouter([
  {
    path: '*',
    element: <NoticePage />,
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
