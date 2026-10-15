# memory-eval-v1

Labelled retrieval dataset for Memory Merge. 240 memories (`corpus.jsonl`) and 160 queries with
graded relevance (`queries.jsonl`); format in docs/DATA_FORMATS.md, results in docs/EVALUATION.md.

- **Origin.** Written on 2026-10-13 for this project by a separate agent that was given the use case
  (a personal memory store for coding agents, several projects plus a personal scope) but not told
  how retrieval is implemented. Frozen before any tuning.
- **Content.** Invented projects (atlas, bamboo, cobalt, delta) and invented personal preferences.
  No real people, contact details, credentials or user data. Six memories (tag `suspicious`) contain
  planted prompt-injection text on purpose.
- **Splits.** 64 dev / 96 test queries, 40/60 within every query type. Tune on dev, report test.
- **Known biases.** One annotator; grade-1 labels are judgement calls; queries per project are uneven
  (cobalt 42, @user 18); synthetic text is cleaner than real notes.
- **License.** MIT, like the rest of the repository.

SHA-256 at freeze: `corpus.jsonl` 0164c17560835c9135185ff61a0c22a674cee4adc287593aa9baed28f34f64a1,
`queries.jsonl` f37e7dc349a01e7a6feb51344f38d2e6f81437e3fefe8c925fd0005efe3982a3.
