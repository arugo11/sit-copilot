# Lecture QA Quantitative Evaluation

- Run ID: `2026-03-10_142421`
- Generated At: `2026-03-10T14:24:21.018540`

## Backend Summary

| Variant | Retrieval Backend | Fallback Used | Wait(s) | hit@1 | hit@3 | MRR | no_source_rate | unsupported_answer_rate | post_build_no_source_rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25_whitespace_current | bm25_local | no | 0 | 0.00 | 0.00 | 0.00 | 1.00 | 0.80 | 1.00 |
| bm25_hybrid_bigram | bm25_local | yes | 0 | 0.75 | 1.00 | 0.88 | 0.00 | 0.20 | 0.00 |
| azure_only | azure_search | no | 0 | 0.50 | 0.50 | 0.50 | 0.40 | 0.60 | 0.40 |
| azure_plus_local_fallback_immediate | api_runtime | yes | 0 | 0.50 | 0.50 | 0.50 | 0.60 | 0.40 | 0.60 |
| azure_plus_local_fallback_delayed | api_runtime | yes | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 |

## bm25_whitespace_current

| Case | Retrieval Pass@1 | Retrieval Pass@3 | RR | Answer Pass | Failure Reason | Retrieved Sources |
|---|---:|---:|---:|---:|---|---|
| transformer_q1 | no | no | 0.00 | no | wrong_abstain | - |
| transformer_q2 | no | no | 0.00 | no | wrong_abstain | - |
| transformer_q3 | no | no | 0.00 | yes | - | - |
| transformer_q4 | no | no | 0.00 | no | wrong_abstain | - |
| transformer_q5 | no | no | 0.00 | no | wrong_abstain | - |

## bm25_hybrid_bigram

| Case | Retrieval Pass@1 | Retrieval Pass@3 | RR | Answer Pass | Failure Reason | Retrieved Sources |
|---|---:|---:|---:|---:|---|---|
| transformer_q1 | yes | yes | 1.00 | yes | - | chunk-1, chunk-2, chunk-3 |
| transformer_q2 | yes | yes | 1.00 | yes | - | chunk-1, chunk-3 |
| transformer_q3 | no | no | 0.00 | yes | - | chunk-1, chunk-3, chunk-2 |
| transformer_q4 | yes | yes | 1.00 | yes | - | chunk-2, chunk-3, chunk-1 |
| transformer_q5 | no | yes | 0.50 | no | answerer_failure | chunk-1, chunk-2, chunk-3 |

## azure_only

| Case | Retrieval Pass@1 | Retrieval Pass@3 | RR | Answer Pass | Failure Reason | Retrieved Sources |
|---|---:|---:|---:|---:|---|---|
| transformer_q1 | no | no | 0.00 | no | retrieval_miss | - |
| transformer_q2 | no | no | 0.00 | no | retrieval_miss | - |
| transformer_q3 | no | no | 0.00 | no | hallucinated_detail | 0157cf89-6067-4e82-ba55-9ce185d78732, aefc0bdd-8659-429e-aeb4-183bbf57a9ed, 1b0f8add-f4ea-40c2-8655-774a4d32da56 |
| transformer_q4 | yes | yes | 1.00 | yes | - | 1b0f8add-f4ea-40c2-8655-774a4d32da56, 0157cf89-6067-4e82-ba55-9ce185d78732, aefc0bdd-8659-429e-aeb4-183bbf57a9ed |
| transformer_q5 | yes | yes | 1.00 | yes | - | 1b0f8add-f4ea-40c2-8655-774a4d32da56, 0157cf89-6067-4e82-ba55-9ce185d78732, aefc0bdd-8659-429e-aeb4-183bbf57a9ed |

## azure_plus_local_fallback_immediate

| Case | Retrieval Pass@1 | Retrieval Pass@3 | RR | Answer Pass | Failure Reason | Retrieved Sources |
|---|---:|---:|---:|---:|---|---|
| transformer_q1 | no | no | 0.00 | no | wrong_abstain | - |
| transformer_q2 | no | no | 0.00 | no | wrong_abstain | - |
| transformer_q3 | no | no | 0.00 | yes | - | - |
| transformer_q4 | yes | yes | 1.00 | yes | - | 1b0f8add-f4ea-40c2-8655-774a4d32da56, 0157cf89-6067-4e82-ba55-9ce185d78732 |
| transformer_q5 | yes | yes | 1.00 | yes | - | 1b0f8add-f4ea-40c2-8655-774a4d32da56, aefc0bdd-8659-429e-aeb4-183bbf57a9ed |

## azure_plus_local_fallback_delayed

| Case | Retrieval Pass@1 | Retrieval Pass@3 | RR | Answer Pass | Failure Reason | Retrieved Sources |
|---|---:|---:|---:|---:|---|---|
| transformer_q1 | yes | yes | 1.00 | yes | - | aefc0bdd-8659-429e-aeb4-183bbf57a9ed, 0157cf89-6067-4e82-ba55-9ce185d78732 |
| transformer_q2 | yes | yes | 1.00 | yes | - | aefc0bdd-8659-429e-aeb4-183bbf57a9ed, 0157cf89-6067-4e82-ba55-9ce185d78732 |
| transformer_q3 | no | no | 0.00 | yes | - | aefc0bdd-8659-429e-aeb4-183bbf57a9ed, 0157cf89-6067-4e82-ba55-9ce185d78732 |
| transformer_q4 | yes | yes | 1.00 | yes | - | 1b0f8add-f4ea-40c2-8655-774a4d32da56, 0157cf89-6067-4e82-ba55-9ce185d78732 |
| transformer_q5 | yes | yes | 1.00 | yes | - | 1b0f8add-f4ea-40c2-8655-774a4d32da56, aefc0bdd-8659-429e-aeb4-183bbf57a9ed |
