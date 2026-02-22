type CitationType = 'audio' | 'slide' | 'board' | 'ocr'

export interface ReviewCitationPreview {
  citationId: string
  type: CitationType
  label: string
  tsStartMs?: number
  tsEndMs?: number
}

export interface ReviewSourceViewItem {
  citationId: string
  title: string
  transcript: string
  snapshot: string
}

export const FALLBACK_REVIEW_SOURCE_ITEM: ReviewSourceViewItem = {
  citationId: 'c_default',
  title: 'ソース未選択',
  transcript: '引用元を選択するとここに詳細を表示します。',
  snapshot: 'https://dummyimage.com/640x360/e2e8f0/0f172a&text=Source+Preview',
}

const SOURCE_SNAPSHOTS: Record<CitationType, string> = {
  audio: 'https://dummyimage.com/640x360/e2e8f0/0f172a&text=Audio+Evidence',
  slide: 'https://dummyimage.com/640x360/cbd5e1/0f172a&text=Slide+Evidence',
  board: 'https://dummyimage.com/640x360/94a3b8/0f172a&text=Board+Evidence',
  ocr: 'https://dummyimage.com/640x360/64748b/f8fafc&text=OCR+Evidence',
}

const SOURCE_TRANSCRIPTS: Record<CitationType, string> = {
  audio: '音声区間の根拠を表示しています。',
  slide: '投影資料の根拠を表示しています。',
  board: '板書キャプチャの根拠を表示しています。',
  ocr: 'OCR抽出テキストの根拠を表示しています。',
}

export const DEFAULT_REVIEW_SOURCE_ITEMS: ReviewSourceViewItem[] = [
  {
    citationId: 'c_static_1',
    title: '発言 10:05',
    transcript: 'これはデモ文です（根拠表示サンプル1）。',
    snapshot: 'https://dummyimage.com/640x360/e2e8f0/0f172a&text=Lecture+Source',
  },
  {
    citationId: 'c_static_2',
    title: '資料 p.3',
    transcript: 'これはデモ文です（根拠表示サンプル2）。',
    snapshot: 'https://dummyimage.com/640x360/cbd5e1/0f172a&text=Slide+p3',
  },
]

export function buildReviewSourceFromCitation(
  citation: ReviewCitationPreview
): ReviewSourceViewItem {
  const startMs = citation.tsStartMs
  const endMs = citation.tsEndMs
  const hasRange = typeof startMs === 'number' && typeof endMs === 'number'
  const timeRange = hasRange
    ? ` (${Math.floor(startMs / 1000)}s-${Math.floor(endMs / 1000)}s)`
    : ''

  return {
    citationId: citation.citationId,
    title: citation.label,
    transcript: `${SOURCE_TRANSCRIPTS[citation.type]}${timeRange}`,
    snapshot: SOURCE_SNAPSHOTS[citation.type],
  }
}
