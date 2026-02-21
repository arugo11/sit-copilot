/**
 * Lectures List Page
 * Based on docs/frontend.md Section 8.2
 */

import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useLectures } from '@/lib/api/hooks'
import type { Lecture } from '@/lib/api/client'
import { EmptyState } from '@/components/common/EmptyState'
import { Skeleton, CardSkeleton } from '@/components/common/Skeleton'

type LectureStatus = 'upcoming' | 'live' | 'ended'
type FilterType = 'all' | LectureStatus

function getStatusBadge(status: LectureStatus) {
  const variants = {
    upcoming: 'badge-default',
    live: 'badge-danger',
    ended: 'badge-success',
  }
  const labels = {
    upcoming: '予定',
    live: 'ライブ中',
    ended: '終了',
  }
  return (
    <span className={`badge ${variants[status]}`}>
      {labels[status]}
    </span>
  )
}

function LectureCard({ lecture }: { lecture: Lecture }) {
  return (
    <Link
      to={lecture.status === 'live' ? `/lectures/${lecture.lectureId}/live` : `/lectures/${lecture.lectureId}/review`}
      className="card block hover:shadow-md transition-shadow"
    >
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-lg font-semibold text-fg-primary line-clamp-2">
              {lecture.title}
            </h3>
            {getStatusBadge(lecture.status)}
          </div>
          <p className="text-sm text-fg-secondary">{lecture.instructor}</p>
        </div>

        {/* Details */}
        <div className="space-y-1 text-sm text-fg-secondary">
          <p>
            <span role="img" aria-label="場所">📍</span> {lecture.room}
          </p>
          <p>
            <span role="img" aria-label="日時">🕐</span> {new Date(lecture.startAt).toLocaleDateString('ja-JP')}
          </p>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-2">
          {lecture.languageTags.map((tag) => (
            <span key={tag} className="badge badge-default text-xs">
              {tag}
            </span>
          ))}
          {lecture.accessibilityTags.map((tag) => (
            <span key={tag} className="badge badge-success text-xs">
              {tag}
            </span>
          ))}
        </div>

        {/* CTA */}
        <div className="btn btn-primary w-full text-center">
          {lecture.status === 'live' ? '講義に入る' : 'レビューを見る'}
        </div>
      </div>
    </Link>
  )
}

export function LecturesPage() {
  const [filter, setFilter] = useState<FilterType>('all')

  // Fetch lectures from API
  const { data: lectures, isLoading, error, refetch } = useLectures(
    filter !== 'all' ? { status: filter } : undefined
  )

  // Show error state
  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
          <p className="text-fg-secondary">受講中の講義、予定、過去の講義を確認できます</p>
        </div>
        <EmptyState
          variant="error"
          title="講義データの読み込みに失敗しました"
          description={error.message || 'ネットワーク接続を確認してください'}
          action={
            <button onClick={() => refetch()} className="btn btn-primary">
              再試行
            </button>
          }
        />
      </div>
    )
  }

  // Show loading state with skeletons
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
          <p className="text-fg-secondary">受講中の講義、予定、過去の講義を確認できます</p>
        </div>

        {/* Filters Skeleton */}
        <div className="flex gap-4 mb-6">
          <Skeleton className="h-10 w-20" />
          <Skeleton className="h-10 w-20" />
          <Skeleton className="h-10 w-20" />
          <Skeleton className="h-10 w-20" />
        </div>

        {/* Cards Grid Skeleton */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    )
  }

  // No lectures found
  if (!lectures || lectures.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
          <p className="text-fg-secondary">受講中の講義、予定、過去の講義を確認できます</p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-6" role="group" aria-label="講義フィルター">
          <button
            onClick={() => setFilter('all')}
            className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'all'}
          >
            すべて
          </button>
          <button
            onClick={() => setFilter('live')}
            className={`btn ${filter === 'live' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'live'}
          >
            ライブ中
          </button>
          <button
            onClick={() => setFilter('upcoming')}
            className={`btn ${filter === 'upcoming' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'upcoming'}
          >
            予定
          </button>
          <button
            onClick={() => setFilter('ended')}
            className={`btn ${filter === 'ended' ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === 'ended'}
          >
            終了
          </button>
        </div>

        <EmptyState
          variant="no-data"
          title="講義がありません"
          description="現在表示できる講義がありません"
        />
      </div>
    )
  }

  // Show lectures
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-fg-primary mb-2">講義一覧</h1>
        <p className="text-fg-secondary">受講中の講義、予定、過去の講義を確認できます</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6" role="group" aria-label="講義フィルター">
        <button
          onClick={() => setFilter('all')}
          className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}
          aria-pressed={filter === 'all'}
        >
          すべて
        </button>
        <button
          onClick={() => setFilter('live')}
          className={`btn ${filter === 'live' ? 'btn-primary' : 'btn-ghost'}`}
          aria-pressed={filter === 'live'}
        >
          ライブ中
        </button>
        <button
          onClick={() => setFilter('upcoming')}
          className={`btn ${filter === 'upcoming' ? 'btn-primary' : 'btn-ghost'}`}
          aria-pressed={filter === 'upcoming'}
        >
          予定
        </button>
        <button
          onClick={() => setFilter('ended')}
          className={`btn ${filter === 'ended' ? 'btn-primary' : 'btn-ghost'}`}
          aria-pressed={filter === 'ended'}
        >
          終了
        </button>
      </div>

      {/* Lecture Cards Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {lectures.map((lecture) => (
          <LectureCard key={lecture.lectureId} lecture={lecture} />
        ))}
      </div>
    </div>
  )
}
