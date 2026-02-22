export type LiveLangMode = 'ja' | 'easy-ja' | 'en'

const EN_GLOSSARY: Array<[RegExp, string]> = [
  [/機械学習/g, 'machine learning'],
  [/過学習/g, 'overfitting'],
  [/正則化/g, 'regularization'],
  [/検証データ/g, 'validation data'],
  [/訓練データ/g, 'training data'],
  [/未知データ/g, 'unseen data'],
]

const EASY_JA_GLOSSARY: Array<[RegExp, string]> = [
  [/機械学習/g, 'AIの学習'],
  [/過学習/g, '学びすぎ（過学習）'],
  [/正則化/g, '調整（正則化）'],
  [/検証データ/g, 'チェック用データ'],
  [/訓練データ/g, '学習用データ'],
  [/未知データ/g, 'はじめてのデータ'],
]

export function translateForLiveView(text: string, mode: LiveLangMode): string {
  const source = text.trim()
  if (!source || mode === 'ja') {
    return source
  }

  if (mode === 'easy-ja') {
    let out = source
    for (const [pattern, replacement] of EASY_JA_GLOSSARY) {
      out = out.replace(pattern, replacement)
    }
    return out
  }

  let out = source
  for (const [pattern, replacement] of EN_GLOSSARY) {
    out = out.replace(pattern, replacement)
  }
  return `[EN] ${out}`
}
