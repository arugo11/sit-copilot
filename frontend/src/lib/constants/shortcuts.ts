/**
 * Keyboard Shortcuts Constants
 * Predefined keyboard shortcuts for the lecture application
 */

import type { ShortcutItem } from '@/components/common/KeyboardShortcutsHelp'

export const lectureShortcuts: ShortcutItem[] = [
  // Navigation
  { keys: ['/'], description: { ja: '検索ボックスにフォーカス', en: 'Focus search' }, category: 'navigation' },
  { keys: ['Escape'], description: { ja: 'ダイアログを閉じる', en: 'Close dialog' }, category: 'navigation' },
  { keys: ['ArrowUp', 'ArrowDown'], description: { ja: '字幕をスクロール', en: 'Scroll transcript' }, category: 'navigation' },

  // Actions
  { keys: ['Control', 'k'], description: { ja: '質問入力を開く', en: 'Open question input' }, category: 'action' },
  { keys: ['Control', ','], description: { ja: '設定を開く', en: 'Open settings' }, category: 'action' },
  { keys: ['Enter'], description: { ja: '質問を送信', en: 'Submit question' }, category: 'action' },

  // Accessibility
  { keys: ['Control', 'Shift', 'T'], description: { ja: 'テーマを切り替え', en: 'Toggle theme' }, category: 'accessibility' },
  { keys: ['Control', '='], description: { ja: '文字サイズを拡大', en: 'Increase font size' }, category: 'accessibility' },
  { keys: ['Control', '-'], description: { ja: '文字サイズを縮小', en: 'Decrease font size' }, category: 'accessibility' },
]
