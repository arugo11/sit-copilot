# Lecture QA Latency Report

- Run ID: `2026-03-10_143056`
- Generated At: `2026-03-10T14:30:56.014010`
- Session ID: `lec_20260310_4caf0f`
- Post-build Wait: `5s`

## Phase Summary

| Phase | Count | Min (ms) | Median (ms) | Mean (ms) | P95 (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|---:|
| bootstrap | 1 | 48.7 | 48.7 | 48.7 | 48.7 | 48.7 |
| session_start | 1 | 36.2 | 36.2 | 36.2 | 36.2 | 36.2 |
| speech_ingest | 3 | 34.6 | 34.8 | 35.1 | 35.8 | 35.9 |
| index_build | 1 | 167.7 | 167.7 | 167.7 | 167.7 | 167.7 |
| azure_search | 5 | 45.0 | 47.9 | 71.2 | 112.8 | 115.5 |
| qa_ask_immediate | 5 | 61.5 | 1856.4 | 12651.0 | 47421.6 | 58619.3 |
| qa_ask_delayed | 5 | 3167.8 | 18004.7 | 16560.6 | 31801.8 | 34853.0 |

## Detailed Samples

| Phase | Label | Latency (ms) | Status | Detail |
|---|---|---:|---|---|
| bootstrap | bootstrap | 48.7 | ok |  |
| session_start | session_start | 36.2 | ok |  |
| speech_ingest | chunk_1 | 35.9 | ok | chars=65 |
| speech_ingest | chunk_2 | 34.6 | ok | chars=221 |
| speech_ingest | chunk_3 | 34.8 | ok | chars=266 |
| index_build | index_build | 167.7 | ok |  |
| azure_search | トランスフォーマーはいつ発表された? | 115.5 | ok | hits=0 |
| qa_ask_immediate | transformer_q1 | 86.7 | ok | sources=0 confidence=low |
| azure_search | トランスフォーマーは誰が発表した? | 47.9 | ok | hits=3 |
| qa_ask_immediate | transformer_q2 | 61.5 | ok | sources=0 confidence=low |
| azure_search | トランスフォーマーはどの国で開発された/ | 45.4 | ok | hits=3 |
| qa_ask_immediate | transformer_q3 | 1856.4 | ok | sources=2 confidence=medium |
| azure_search | どのようなタスクで用いられれる? | 102.1 | ok | hits=3 |
| qa_ask_immediate | transformer_q4 | 2630.9 | ok | sources=2 confidence=medium |
| azure_search | トランスフォーマーのはなぜトレーニング時間が短縮される? | 45.0 | ok | hits=3 |
| qa_ask_immediate | transformer_q5 | 58619.3 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q1 | 3167.8 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q2 | 18004.7 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q3 | 34853.0 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q4 | 7180.3 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q5 | 19597.0 | ok | sources=2 confidence=medium |

## Observations

- `azure_search` は retrieval 単体の往復時間で、`qa_ask_*` は retrieval と生成を含む API 全体の時間です。
- `qa_ask_immediate` と `qa_ask_delayed` の差は、主に index 可視化遅延と生成負荷の差を見ています。
- `qa_ask_*` が `azure_search` より大幅に遅い場合、ボトルネックは retrieval ではなく answer/verifier 系である可能性が高いです。
- 今回の計測では `qa_ask_immediate` 平均 12651.0ms に対し `qa_ask_delayed` 平均 16560.6ms でした。
- `azure_search` 平均は 71.2ms で、QA API より十分小さいため、体感遅延の主因は生成側です。
