# Lecture QA Latency Report

- Run ID: `2026-03-10_145548`
- Generated At: `2026-03-10T14:55:48.373562`
- Session ID: `lec_20260310_9067ed`
- Post-build Wait: `5s`

## Phase Summary

| Phase | Count | Min (ms) | Median (ms) | Mean (ms) | P95 (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|---:|
| bootstrap | 1 | 18404.8 | 18404.8 | 18404.8 | 18404.8 | 18404.8 |
| session_start | 1 | 292.5 | 292.5 | 292.5 | 292.5 | 292.5 |
| speech_ingest | 3 | 33.9 | 44.6 | 536.5 | 1382.3 | 1530.9 |
| index_build | 1 | 443.4 | 443.4 | 443.4 | 443.4 | 443.4 |
| azure_search | 5 | 42.8 | 45.1 | 58.7 | 91.4 | 98.2 |
| qa_ask_immediate | 5 | 57.3 | 62.8 | 524.3 | 1916.4 | 2379.6 |
| qa_ask_delayed | 5 | 805.8 | 2670.5 | 23490.0 | 57501.6 | 58412.0 |

## Detailed Samples

| Phase | Label | Latency (ms) | Status | Detail |
|---|---|---:|---|---|
| bootstrap | bootstrap | 18404.8 | ok |  |
| session_start | session_start | 292.5 | ok |  |
| speech_ingest | chunk_1 | 44.6 | ok | chars=65 |
| speech_ingest | chunk_2 | 33.9 | ok | chars=221 |
| speech_ingest | chunk_3 | 1530.9 | ok | chars=266 |
| index_build | index_build | 443.4 | ok |  |
| azure_search | トランスフォーマーはいつ発表された? | 98.2 | ok | hits=0 |
| qa_ask_immediate | transformer_q1 | 62.8 | ok | sources=0 confidence=low |
| azure_search | トランスフォーマーは誰が発表した? | 43.0 | ok | hits=3 |
| qa_ask_immediate | transformer_q2 | 63.7 | ok | sources=0 confidence=low |
| azure_search | トランスフォーマーはどの国で開発された/ | 64.5 | ok | hits=0 |
| qa_ask_immediate | transformer_q3 | 57.3 | ok | sources=0 confidence=low |
| azure_search | どのようなタスクで用いられれる? | 45.1 | ok | hits=3 |
| qa_ask_immediate | transformer_q4 | 58.1 | ok | sources=0 confidence=low |
| azure_search | トランスフォーマーのはなぜトレーニング時間が短縮される? | 42.8 | ok | hits=0 |
| qa_ask_immediate | transformer_q5 | 2379.6 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q1 | 53860.2 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q2 | 805.8 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q3 | 1701.5 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q4 | 58412.0 | ok | sources=2 confidence=medium |
| qa_ask_delayed | transformer_q5 | 2670.5 | ok | sources=2 confidence=medium |

## Observations

- `azure_search` は retrieval 単体の往復時間で、`qa_ask_*` は retrieval と生成を含む API 全体の時間です。
- `qa_ask_immediate` と `qa_ask_delayed` の差は、主に index 可視化遅延と生成負荷の差を見ています。
- `qa_ask_*` が `azure_search` より大幅に遅い場合、ボトルネックは retrieval ではなく answer/verifier 系である可能性が高いです。
- 今回の計測では `qa_ask_immediate` 平均 524.3ms に対し `qa_ask_delayed` 平均 23490.0ms でした。
- `azure_search` 平均は 58.7ms で、QA API より十分小さいため、体感遅延の主因は生成側です。
