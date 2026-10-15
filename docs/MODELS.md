# Models

Memory Merge needs no model: lexical retrieval is the default. Two optional roles exist:
**embeddings** (semantic and cross-lingual recall) and a **judge** (advice for the review queue).
This document records what was verified, what was measured, and the decisions taken. Commands
reproduce every number; JSON results are in `docs/eval/`.

## Summary of decisions

| Question (from the brief) | Decision | Evidence |
|---|---|---|
| Which embedding model | Qwen3-Embedding-0.6B, official weights or the official Q8_0 GGUF | provenance verified below; test nDCG@10 0.827 |
| Pooling | last token (EOS), as the model's configuration defines; servers must use `--pooling last` | model card, `1_Pooling/config.json`; parity check below |
| Normalisation | L2, always applied client-side after truncation | `vectors.normalize` |
| MRL dimension | native 1024 by default; 512 is a safe storage halving | dev +0.013 / test -0.009 nDCG: no measurable difference |
| Query instruction | required for best quality, not for correctness: `Instruct: {task}\nQuery:{text}`, documents plain | dev +0.017 nDCG with it |
| Model swaps | fingerprint of backend, model, revision, pooling, dimension, document template + canary vectors | `test_service` drift test |
| Batching, caching, reuse | 32 texts per request; incremental indexing (only memories without a current-fingerprint vector); matrix cached in long-running servers; judge advice cached per content and model | `test_service` incremental test |
| Local runtime without a server | sentence-transformers in process (executed, matches reference); llama.cpp in process (implemented, not executed) | parity check below |
| Quantisation, embeddings | Q8_0 is enough: cosine >= 0.9988 to the fp32 reference, test nDCG 0.827 vs 0.830 | parity check below |
| Which judge model | **none by default**. If used: an official model such as Qwen3-1.7B Q8_0 with the judge-v3 prompt | held-out category agreement 71%, injection detection weak |
| Judge schema strictness | strict: required keys, enumerations, ranges; unknown keys rejected; fail closed | `test_service` |
| Thinking models | disable thinking (`MM_JUDGE_NO_THINK=1`) | thinking: 48% valid; no-think: 100% valid, 2.5x faster |
| When to invoke the judge | never on capture or recall; on demand for the review queue, cached | latency 1.3 s/memory on GPU |
| Calibrated importance | shown only as an uncalibrated hint until 30+ of the user's own decisions calibrate it | judge-v2 importance was flat; judge-v3 spreads it, predictive value unmeasured |

## Embeddings: Qwen3-Embedding-0.6B

### Provenance (verified 2026-10-13)

| Artifact | Official source | SHA-256 | Size |
|---|---|---|---|
| `model.safetensors` | `Qwen/Qwen3-Embedding-0.6B` @ 97b0c614be4d (Apache-2.0) | `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd` | 1,191,586,416 |
| `Qwen3-Embedding-0.6B-Q8_0.gguf` | `Qwen/Qwen3-Embedding-0.6B-GGUF` @ 370f27d7550e | `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439` | 639,150,592 |
| Ollama `qwen3-embedding:0.6b` | registry layer | identical to the official Q8_0 GGUF above | |

Both files used in measurement were downloaded and re-hashed locally; both matched. There is no
official ONNX export; community exports (onnx-community, Qdrant) pin no upstream revision and one
declares no license, so none is recommended. The official GGUFs were replaced on 2025-07-14; older
copies have different hashes (`a0e820fb...` for Q8_0), which is one reason the fingerprint includes
the revision.

### Model-card facts the implementation depends on

Last-token pooling over an EOS token the tokenizer appends; query-side instruction
`Instruct: {task}\nQuery:{query}` (no space after `Query:`), no instruction on documents; the card
recommends English task text even for other languages; output dimension 1024, Matryoshka truncation
supported from 32 to 1024 (truncate first, then L2-normalise, as the official evaluation code does);
context 32k (the official evaluation uses 8,192, which the sentence-transformers backend pins
because the repository does not).

### Measured retrieval

See docs/EVALUATION.md: test nDCG@10 0.827 (vector/hybrid, 1024 dims) vs 0.649 lexical and 0.340
for 0.1; cross-lingual 0.914 vs 0.479 lexical; paraphrase 0.708 vs 0.403.

### Runtime paths

| Path | Configuration | Status |
|---|---|---|
| OpenAI-compatible HTTP (Ollama, llama.cpp server, vLLM, LM Studio, TEI) | `MM_EMBED_URL`, `MM_EMBED_MODEL`, `MM_EMBED_PRESET=qwen3-embedding` | **measured** (Ollama 0.30.10, GPU) |
| sentence-transformers, in process | `MM_EMBED_BACKEND=sentence-transformers` | **executed** in the parity check (fp32, CPU) |
| llama.cpp (`llama-cpp-python`), in process | `MM_EMBED_BACKEND=llama-cpp`, `MM_EMBED_PATH=*.gguf` | **not executed** (build failed on this machine; see "llama.cpp status") |

Remote providers need HTTPS and `MM_ALLOW_REMOTE=1`; see docs/THREAT_MODEL.md (T3).

## Judge

### The model named in the brief

"Qwen3.8-2B-distill" is **not an official Qwen model**. The only match is
`empero-ai/Qwen3.8-2B-Distill` (and a `-GGUF` repo): a single-commit community fine-tune of
`Qwen/Qwen3.5-2B`, said to be distilled from a large Qwen3.8 model on undisclosed data; its
benchmark claims are self-reported; its GGUF files are named like official releases; its Apache-2.0
claim does not address the teacher model's license. It was not used. The official Qwen3.8 family
has no 2B model (verified via the Hugging Face API).

### What was measured instead

Official `Qwen/Qwen3-1.7B-GGUF` Q8_0 (SHA-256 `061b54da...90cb1a`, re-hashed locally, matched),
served by Ollama with a 4,096-token context, on all 240 memories of the evaluation corpus, first with
the judge-v2 prompt (the prompt comparison follows below):

```bash
python bench/judge_eval.py --model <ollama model> --strategies "json_schema+no_think,none+no_think,json_object+no_think" --out docs/eval/judge-qwen3-1.7b-nothink.json
python bench/judge_eval.py --model <ollama model> --strategies json_schema --limit 60 --out docs/eval/judge-qwen3-1.7b-thinking-60.json
```

| Response strategy | valid (rest fail closed) | category agreement | injections flagged | false flags | p50 latency |
|---|---|---|---|---|---|
| JSON schema, thinking off | 100% | 46.3% | 0 / 6 | 0 / 234 | 1.27 s |
| unconstrained, thinking off | 100% | 46.7% | 0 / 6 | 0 / 234 | 1.61 s |
| JSON object, thinking off | 100% | 46.7% | 0 / 6 | 0 / 234 | 1.41 s |
| JSON schema, thinking on (60 memories) | 48.3% | 48.3% of valid | 0 / 2 | 0 / 27 | 3.23 s |

Findings:

1. **Fail-closed works, and thinking is what breaks validity.** Every failure with thinking on was a
   reply cut off at the token limit while still reasoning (`finish_reason: length`, empty content);
   the parser rejected it and the memory simply stayed pending. With thinking off all replies
   validated. One server artefact (a bare leading `</think>` when thinking is disabled) is now
   tolerated; anything else around the JSON is still rejected.
2. **Category agreement is low** (46%; "agreement with one annotator", not accuracy). The judge
   over-predicts `knowledge` (86 predicted vs 16 labelled), mostly for facts (46 cases).
3. **Importance carries almost no information**: mean 0.67-0.70 in every category, and the same
   pattern under all strategies. Durability was "durable" for 234 of 240.
4. **It flagged none of the 6 planted prompt-injection notes.** The regex flag
   (`text.instruction_like`) is the only injection signal that fires on them; the judge does not
   replace it.
5. Response format barely matters once thinking is off; JSON schema was fastest.

Prompt anchoring was suspected (the first few-shot example has importance 0.7):
it was tested, on halves of the corpus so that the prompt was chosen on one half and reported on the
other:

```bash
python bench/judge_prompt_ablation.py --model <ollama model> --out docs/eval/judge-prompt-ablation.json
```

| prompt (JSON schema, thinking off) | half | category agreement | importance std | distinct importance values | injections flagged | false flags |
|---|---|---|---|---|---|---|
| judge-v2: 2 examples (importance 0.7, 0.1) | tune | 48.3% | 0.062 | 2 | 0 / 3 | 0 / 117 |
| zero-shot | tune | 37.8% | 0.051 | 3 | 0 / 3 | 1 / 116 |
| 6 diverse examples | tune | 63.3% | 0.163 | 7 | 0 / 3 | 0 / 117 |
| judge-v2 | **held out** | 45.8% | 0.062 | 2 | 0 / 3 | 0 / 117 |
| **6 diverse examples (adopted as judge-v3)** | **held out** | **70.8%** | 0.181 | 8 | 1 / 3 | 0 / 117 |

The examples, not their absence, drive behaviour: zero-shot was worse, and the two-example prompt
made the model copy the first example's importance. `judge-v3` (six examples covering preference,
procedure, ephemeral state, lesson, injection and a plain fact, importances 0.1-0.9) raised held-out
agreement from 46% to 71% and gave importance a real spread. Injection detection stayed weak (1 of
3). Changing the prompt changes the judge fingerprint, so cached judge-v2 advice is not reused.

### Recommendation

The judge stays **off by default**. With `judge-v3`, a 1.7B model gives category suggestions that
agree with the dataset labels 71% of the time and an importance score with some spread, at about
1 s per memory on a GPU. Whether that importance predicts *your* approvals is unknown until
`memory-merge judge-calibration` has 30 or more reviewed decisions; until then the queue shows it as
an uncalibrated hint. It does not detect prompt injection reliably (1 of 3 on the held-out half);
the regex flag and human review remain the defences. If you enable it: an official model, thinking
off (`MM_JUDGE_NO_THINK=1`), JSON-schema output, an explicit context size, and its advice never
approves anything.
### Deployment pitfall: context length

Ollama loaded the 1.7B judge with the model's full 40,960-token context: 7.2 GB, partly on CPU on an
8 GB GPU, 15-60 s per call. A derived model with `PARAMETER num_ctx 4096` (the judge prompt is
about 800 tokens) used 2.4 GB, fully on the GPU, about 1.3 s per call. The `OLLAMA_CONTEXT_LENGTH`
server variable did not override the context stored with that model.

### Quantisation for small judges

Only Q8_0 was measured (it is the only quantisation in the official Qwen3-1.7B GGUF repository).
Lower-bit quantisations of a 2B model (Q4_K_M) are generally more likely to break format adherence;
with grammar-constrained decoding that risk turns into worse content rather than invalid JSON. Not
measured here.

## llama.cpp status

`LlamaCppEmbedder` and `LlamaCppJudge` are implemented against the documented llama-cpp-python 0.3
API (embedding with last-token pooling; chat completion with a JSON-schema grammar) but were **not
executed**. Building llama-cpp-python 0.3.36 from source failed twice on the measurement machine:
MSBuild error MSB8084 (it could not parse CL.exe's structured output; Visual Studio 2022 Build Tools
on a Chinese-locale Windows; `VSLANG=1033` did not help). This is a toolchain problem, not a code
problem, but it leaves these two adapters unverified. The same GGUF files *were* exercised through
Ollama, which embeds llama.cpp, so GGUF inference itself is covered by the server path.

## Reference parity: does the served GGUF reproduce the reference?

```bash
python bench/reference_parity.py --reference <snapshot of Qwen/Qwen3-Embedding-0.6B@97b0c614be4d> --out docs/eval/reference-parity.json
```

The same texts were embedded by (a) sentence-transformers on the official fp32 safetensors (CPU),
through Memory Merge's own `SentenceTransformersEmbedder`, which is the model card's reference usage,
and (b) Ollama serving the official Q8_0 GGUF (GPU).

| | n | cosine min | cosine mean | cosine max |
|---|---|---|---|---|
| documents (no instruction) | 40 | 0.9988 | 0.9993 | 0.9995 |
| queries with the Qwen3 instruction | 20 | 0.9990 | 0.9993 | 0.9995 |

Retrieval on the test split with the fp32 reference: nDCG@10 **0.830**, Recall@10 0.885, MRR 0.905,
against **0.827 / 0.887 / 0.899** for the Q8_0 GGUF through Ollama. Per type within 0.003 everywhere
(e.g. cross-lingual 0.916 vs 0.914, paraphrase 0.708 vs 0.708).

Conclusions: the served GGUF path pools and terminates sequences like the reference (this settles
the open question of whether the July 2025 GGUF re-upload appends EOS correctly: it behaves as if it
does); Q8_0 quantisation costs nothing measurable for retrieval here; and the in-process
sentence-transformers backend works end to end (executed, not just written). On CPU it is slow
(p50 0.9 s per query while competing with a compiler for cores; model load 46 s), so the GPU
server path is the practical one on this hardware.
