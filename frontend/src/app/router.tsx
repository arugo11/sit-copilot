/**
 * App Router
 * Based on docs/frontend.md Section 4.1
 */

import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'

// Lazy load pages for code splitting
const LandingPage = lazy(() => import('@/pages/landing/LandingPage').then(m => ({ default: m.LandingPage })))
const LecturesPage = lazy(() => import('@/pages/lectures/LecturesPage').then(m => ({ default: m.LecturesPage })))
const LectureLivePage = lazy(() => import('@/pages/lectures/LectureLivePage').then(m => ({ default: m.LectureLivePage })))
const LectureReviewPage = lazy(() => import('@/pages/lectures/LectureReviewPage').then(m => ({ default: m.LectureReviewPage })))
const LectureSourcesPage = lazy(() => import('@/pages/lectures/LectureSourcesPage').then(m => ({ default: m.LectureSourcesPage })))
const LectureQAPage = lazy(() => import('@/pages/lectures/LectureQAPage').then(m => ({ default: m.LectureQAPage })))
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage').then(m => ({ default: m.SettingsPage })))
const ProcedurePage = lazy(() => import('@/pages/procedure/ProcedurePage').then(m => ({ default: m.ProcedurePage })))
const ReadinessCheckPage = lazy(() => import('@/pages/readiness/ReadinessCheckPage').then(m => ({ default: m.ReadinessCheckPage })))

import { Skeleton } from '@/components/common/Skeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { AppShell } from '@/components/common/AppShell'

// Loading component for lazy loaded routes
function PageLoader() {
  return (
    <div className="p-8">
      <Skeleton variant="card" className="h-64" />
    </div>
  )
}

// Router configuration
const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/lectures',
    element: <LecturesPage />,
  },
  {
    path: '/lectures/:id/live',
    element: <LectureLivePage />,
  },
  {
    path: '/lectures/:id/review',
    element: <LectureReviewPage />,
  },
  {
    path: '/lectures/:id/sources',
    element: <LectureSourcesPage />,
  },
  {
    path: '/lecture/:session_id/qa',
    element: <LectureQAPage />,
  },
  {
    path: '/lectures/:id/qa',
    element: <LectureQAPage />,
  },
  {
    path: '/settings',
    element: <SettingsPage />,
  },
  {
    path: '/procedure',
    element: <ProcedurePage />,
  },
  {
    path: '/readiness-check',
    element: <ReadinessCheckPage />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

function NotFoundPage() {
  return (
    <AppShell>
      <EmptyState
        variant="error"
        title="ページが見つかりません"
        description="お探しのページは存在しないか、移動された可能性があります。"
        action={<a href="/" className="btn btn-primary">ホームに戻る</a>}
      />
    </AppShell>
  )
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <RouterProvider router={router} />
    </Suspense>
  )
}
