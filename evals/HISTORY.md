# Eval history

Every full run, as measured. Failures stay.

| Date | Commit | Model | Passed | Provider failures | Guard hits | Median first token (s) | Median turn (s) | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-10-31 18:22 | 1aff74c | gemini-3.5-flash-lite | 34/47 | 9 | 1 | 1.99 | 2.21 | baseline |
| 2026-10-31 18:39 | 38f79fd | gemini-3.5-flash-lite | 44/47 | 1 | 0 | 1.76 | 1.87 | after first fixes |
| 2026-10-31 18:46 | b4c5b4d | gemini-3.5-flash-lite | 46/47 | 0 | 1 | 1.85 | 2.0 | action guard, parallel calls fixed |
| 2026-10-31 20:04 | 629c755 | gemini-3.5-flash-lite | 47/47 | 0 | 1 | 1.77 | 1.99 | after tone and citation fixes |
| 2026-11-01 17:00 | 4613675 | gemini-3.5-flash-lite | 50/55 | 0 | 0 | 1.96 | 2.14 | bilingual, en cases, low effort |
| 2026-11-01 17:09 | 399c231 | gemini-3.5-flash-lite | 49/55 | 0 | 1 | 1.96 | 2.12 | after fixing marker, order block, named-model search |
