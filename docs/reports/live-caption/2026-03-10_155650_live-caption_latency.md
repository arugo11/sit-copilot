# Live Caption Synthetic Replay Latency Report

- Run ID: `2026-03-10_155650`
- Generated At: `2026-03-10T15:56:50.916035`
- Session ID: `lec_20260310_7c9412`
- Source URL: `https://www.ted.com/pages/sam-altman-on-the-future-of-ai-and-humanity-transcript`
- Chunks Replayed: `10`
- Inter-chunk Delay: `1000ms`

## Interpretation

- 現在の UI は speech recognition の最終結果を `/speech/chunk` へ送信し、その HTTP 応答直後に `applyTranscriptFinal(...)` で字幕を表示します。
- そのため本実験の `subtitle_visible_estimate_ms` は、現行実装における字幕表示遅延の推定値として `ingest_http_ms` と同値です。
- `sse_transcript_final_ms` はサーバー配信の整合確認用で、ローカル表示より遅くても UI の一次表示には直結しません。

## Summary

| Metric | Count | Min (ms) | Median (ms) | Mean (ms) | P95 (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|---:|
| ingest_http_ms | 10 | 35.3 | 38.2 | 47.7 | 87.4 | 120.0 |
| subtitle_visible_estimate_ms | 10 | 35.3 | 38.2 | 47.7 | 87.4 | 120.0 |
| sse_transcript_final_ms | 10 | 596.5 | 1026.3 | 983.8 | 1030.4 | 1030.5 |

- SSE coverage: `100.00%`

## Samples

| Chunk | Chars | ingest_http_ms | subtitle_visible_estimate_ms | sse_transcript_final_ms | Preview |
|---:|---:|---:|---:|---:|---|
| 1 | 138 | 120.0 | 120.0 | 596.5 | Please note the following transcript may not exactly match the final aud |
| 2 | 198 | 35.3 | 35.3 | 1026.9 | [00:00:00] Sam Altman: One of the surprises for me about kind of this tr |
| 3 | 53 | 47.5 | 47.5 | 1030.5 | [00:00:12] Adam Grant: Hey everyone, it's Adam Grant. |
| 4 | 106 | 36.5 | 36.5 | 1023.0 | Welcome back to ReThinking, my podcast on the science of what makes us t |
| 5 | 143 | 39.0 | 39.0 | 1025.9 | I'm an organizational psychologist, and I'm taking you inside the minds  |
| 6 | 59 | 36.6 | 36.6 | 1026.0 | My guest today is Sam Altman, CEO and co-founder of OpenAI. |
| 7 | 73 | 37.5 | 37.5 | 1023.0 | Since Sam and his colleagues first dreamed up ChatGPT, a lot has changed |
| 8 | 194 | 41.3 | 41.3 | 1026.6 | [00:00:37] Sam Altman: You and I are living through this once in human h |
| 9 | 169 | 35.8 | 35.8 | 1030.3 | [00:00:49] Adam Grant: The exponential progress of AI has made me rethin |
| 10 | 88 | 47.3 | 47.3 | 1029.6 | Since the source code is a black box, I figured it was time to go to the |
