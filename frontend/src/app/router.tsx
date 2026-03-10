/**
 * App Router
 * Based on docs/frontend.md Section 4.1
 */

import { lazy, Suspense } from 'react'
import { Navigate, createBrowserRouter, RouterProvider } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

// Lazy load pages for code splitting
const LandingPage = lazy(() => import('@/pages/landing/LandingPage').then(m => ({ default: m.LandingPage })))
const LecturesPage = lazy(() => import('@/pages/lectures/LecturesPage').then(m => ({ default: m.LecturesPage })))
const LectureLivePage = lazy(() => import('@/pages/lectures/LectureLivePage').then(m => ({ default: m.LectureLivePage })))
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage').then(m => ({ default: m.SettingsPage })))

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
    element: <Navigate to="/lectures" replace />,
  },
  {
    path: '/lectures/:id/sources',
    element: <Navigate to="/lectures" replace />,
  },
  {
    path: '/lecture/:session_id/qa',
    element: <Navigate to="/lectures" replace />,
  },
  {
    path: '/lectures/:id/qa',
    element: <Navigate to="/lectures" replace />,
  },
  {
    path: '/settings',
    element: <SettingsPage />,
  },
  {
    path: '/procedure',
    element: <Navigate to="/lectures" replace />,
  },
  {
    path: '/readiness-check',
    element: <Navigate to="/lectures" replace />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

function NotFoundPage() {
  const { t } = useTranslation()

  return (
    <AppShell>
      <EmptyState
        variant="error"
        title={t('notFound.title')}
        description={t('notFound.description')}
        action={<a href="/" className="btn btn-primary">{t('notFound.backHome')}</a>}
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
