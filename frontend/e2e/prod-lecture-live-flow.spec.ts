import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'

type LectureChunk = {
  offset_ms: number
  duration_ms: number
  confidence: number
  speaker: 'teacher' | 'unknown'
  text: string
}

type ScriptExpectations = {
  summary_required_terms: string[]
  keyterms_required: string[]
  supported_qa: {
    question: string
    required_answer_terms: string[]
    required_source_terms: string[]
  }
  unsupported_qa: {
    question: string
    expected_fail_closed_terms: string[]
    disallowed_answer_terms: string[]
  }
}

type LectureScript = {
  session: {
    course_name: string
    lang_mode: 'ja' | 'easy-ja' | 'en'
  }
  speech_chunks: LectureChunk[]
  expected: ScriptExpectations
}

const SCRIPT_PATH = path.resolve(
  __dirname,
  '../../tests/fixtures/lecture_scripts/e2e_fake_lecture_stat_ml_ja.json'
)

function loadLectureScript(): LectureScript {
  const raw = fs.readFileSync(SCRIPT_PATH, 'utf-8')
  return JSON.parse(raw) as LectureScript
}

function pickMatches(candidates: string[], text: string): string[] {
  const lower = text.toLowerCase()
  return candidates.filter((term) => lower.includes(term.toLowerCase()))
}

function parseSessionIdFromLiveUrl(url: string): string {
  const pathname = new URL(url).pathname
  const match = pathname.match(/\/lectures\/([^/]+)\/live/)
  if (!match) {
    throw new Error(`Failed to parse session ID from URL: ${url}`)
  }
  return match[1]
}

test.describe('scenario_prod_web_full_e2e', () => {
  test('runs full lecture flow on production web with scripted API injection', async ({
    page,
    request,
    baseURL,
  }) => {
    const prodApiBaseUrl = process.env.PROD_API_BASE_URL?.trim() ?? ''
    const lectureToken = process.env.E2E_LECTURE_TOKEN?.trim() ?? ''
    const userId = process.env.E2E_USER_ID?.trim() || 'demo-user'

    test.skip(!baseURL, 'PROD_WEB_BASE_URL is required for production web E2E.')
    test.skip(
      !prodApiBaseUrl || !lectureToken,
      'PROD_API_BASE_URL and E2E_LECTURE_TOKEN are required for scripted injection.'
    )

    const script = loadLectureScript()
    const headers = {
      'Content-Type': 'application/json',
      'X-Lecture-Token': lectureToken,
      'X-User-Id': userId,
    }

    let sessionId = ''

    try {
      await page.goto('/lectures', { waitUntil: 'domcontentloaded' })

      const startSessionButton = page.getByRole('button', {
        name: /セッション開始|Start Session/i,
      })
      await expect(startSessionButton).toBeVisible()
      await startSessionButton.click()

      const enterLectureLink = page.getByRole('link', {
        name: /講義に入る|Enter Lecture/i,
      }).first()
      await expect(enterLectureLink).toBeVisible({ timeout: 30_000 })
      await enterLectureLink.click()

      await expect(page).toHaveURL(/\/lectures\/[^/]+\/live/, {
        timeout: 30_000,
      })
      sessionId = parseSessionIdFromLiveUrl(page.url())

      const startRecordingButton = page.getByRole('button', {
        name: /録音開始|Start Recording/i,
      })
      await expect(startRecordingButton).toBeVisible()
      await startRecordingButton.click()
      await expect(
        page.getByRole('button', {
          name: /セッション終了|End Session/i,
        })
      ).toBeVisible({ timeout: 20_000 })

      const nowMs = Date.now()
      for (const chunk of script.speech_chunks) {
        const response = await request.post(
          `${prodApiBaseUrl}/api/v4/lecture/speech/chunk`,
          {
            headers,
            data: {
              session_id: sessionId,
              start_ms: nowMs + chunk.offset_ms,
              end_ms: nowMs + chunk.offset_ms + chunk.duration_ms,
              text: chunk.text,
              confidence: chunk.confidence,
              is_final: true,
              speaker: chunk.speaker,
            },
          }
        )
        expect(response.ok()).toBeTruthy()
        const payload = (await response.json()) as { accepted?: boolean }
        expect(payload.accepted).toBeTruthy()
        await page.waitForTimeout(150)
      }

      const indexBuildResponse = await request.post(
        `${prodApiBaseUrl}/api/v4/lecture/qa/index/build`,
        {
          headers,
          data: {
            session_id: sessionId,
            rebuild: true,
          },
        }
      )
      expect(indexBuildResponse.ok()).toBeTruthy()

      const summarySwitch = page.getByRole('switch', {
        name: /要約機能の切り替え|Toggle summary feature/i,
      })
      await expect(summarySwitch).toBeVisible()
      if ((await summarySwitch.getAttribute('aria-checked')) !== 'true') {
        await summarySwitch.click()
      }

      const refreshNowButton = page.getByRole('button', {
        name: /今すぐ更新|Refresh Now/i,
      })
      await expect(refreshNowButton).toBeVisible()
      await refreshNowButton.click()

      const summarySection = page
        .locator('section')
        .filter({
          has: page.getByRole('heading', {
            name: /いまの要点|Current Key Points/i,
          }),
        })
        .first()

      await expect
        .poll(
          async () => summarySection.locator('li').count(),
          { timeout: 60_000 }
        )
        .toBeGreaterThan(0)

      const summaryText = await summarySection.innerText()
      expect(
        pickMatches(script.expected.summary_required_terms, summaryText).length
      ).toBeGreaterThan(0)

      const keytermsSwitch = page.getByRole('switch', {
        name: /用語抽出機能の切り替え|Toggle key term extraction feature/i,
      })
      await expect(keytermsSwitch).toBeVisible()
      if ((await keytermsSwitch.getAttribute('aria-checked')) === 'true') {
        await keytermsSwitch.click()
      }
      await keytermsSwitch.click()

      const keytermsSection = page
        .locator('section')
        .filter({
          has: page.getByRole('heading', {
            name: /用語サポート|Key Term Support/i,
          }),
        })
        .first()

      await expect
        .poll(
          async () => keytermsSection.locator('li').count(),
          { timeout: 60_000 }
        )
        .toBeGreaterThan(0)

      const keytermsText = await keytermsSection.innerText()
      expect(
        pickMatches(script.expected.keyterms_required, keytermsText).length
      ).toBeGreaterThan(0)

      const qaInput = page.getByLabel(/ミニ質問|Mini Question/i)
      const qaSubmit = page.getByRole('button', {
        name: /送信|Submit/i,
      })

      await qaInput.fill(script.expected.supported_qa.question)
      await qaSubmit.click()

      const supportedQaCard = page
        .locator('article')
        .filter({ hasText: `Q. ${script.expected.supported_qa.question}` })
        .first()
      await expect(supportedQaCard).toBeVisible({ timeout: 60_000 })

      await expect
        .poll(
          async () => {
            const text = await supportedQaCard.innerText()
            return !/生成開始待ち|Waiting to start generation/i.test(text)
          },
          { timeout: 60_000 }
        )
        .toBeTruthy()

      const supportedQaText = await supportedQaCard.innerText()
      expect(
        pickMatches(
          script.expected.supported_qa.required_answer_terms,
          supportedQaText
        ).length
      ).toBeGreaterThan(0)
      expect(await supportedQaCard.getByRole('button').count()).toBeGreaterThan(0)

      await qaInput.fill(script.expected.unsupported_qa.question)
      await qaSubmit.click()

      const unsupportedQaCard = page
        .locator('article')
        .filter({ hasText: `Q. ${script.expected.unsupported_qa.question}` })
        .first()
      await expect(unsupportedQaCard).toBeVisible({ timeout: 60_000 })

      await expect
        .poll(
          async () => {
            const text = await unsupportedQaCard.innerText()
            return !/生成開始待ち|Waiting to start generation/i.test(text)
          },
          { timeout: 60_000 }
        )
        .toBeTruthy()

      const unsupportedQaText = await unsupportedQaCard.innerText()
      expect(
        pickMatches(
          script.expected.unsupported_qa.expected_fail_closed_terms,
          unsupportedQaText
        ).length
      ).toBeGreaterThan(0)
      expect(
        pickMatches(
          script.expected.unsupported_qa.disallowed_answer_terms,
          unsupportedQaText
        ).length
      ).toBe(0)
    } finally {
      if (sessionId) {
        await request.post(`${prodApiBaseUrl}/api/v4/lecture/session/finalize`, {
          headers,
          data: {
            session_id: sessionId,
            build_qa_index: false,
          },
        })
      }
    }
  })
})
