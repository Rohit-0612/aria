<div align="center">

# ARIA

**The Journal of Evidence-Grounded Pharmacotherapy**

A multi-agent, retrieval-augmented clinical assistant that answers pharmacotherapy
questions strictly from the textbook evidence — with an inline citation on every
claim, an independently judged grounding score on every answer, and follow-up
questions understood in context.

[**▶ Live demo**](https://rks0612-aria.hf.space) · [How it works](#how-it-works) · [Evaluation](#evaluation) · [Design decisions](#design-decisions) · [Getting started](#getting-started)

[![CI](https://github.com/Rohit-0612/aria/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohit-0612/aria/actions/workflows/ci.yml)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-React_18-3178C6?logo=typescript&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![Qdrant](https://img.shields.io/badge/Qdrant-Cloud-DC244C)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE_streaming-009688?logo=fastapi&logoColor=white)
![Deployed](https://img.shields.io/badge/Deployed-Hugging_Face_Spaces-FFD21E?logo=huggingface&logoColor=black)

<br/>

<img src="docs/screenshots/cover-dark.png" alt="ARIA cover page" width="800"/>

</div>

---

## What it does

ARIA answers clinical pharmacotherapy questions the way a journal publishes evidence.
Its knowledge comes from two reference texts — **DiPiro's Pharmacotherapy: A
Pathophysiologic Approach (12e)** and the **RxPrep NAPLEX Course Book (2025)** —
and every answer is:

- **Taught, not just answered** — a question is broken into the outline a student
  needs (what it is, how it is treated and why, how the drugs work, what to watch
  for), each part is looked up separately, and the answer explains the reasoning
  and defines its terms
- **Generated only from retrieved passages**, never from the model's open-ended memory —
  a short general explanation is allowed only in a block marked *not from the
  textbooks*, and never carries a drug, dose or number
- **Cited inline, claim by claim** — each statement carries a marker that opens the
  exact passage (book, page, text) it was drawn from
- **Independently adjudicated** by a Judge agent that scores the finished answer for
  groundedness, citation accuracy and relevance, shown as a grounding badge and score
- **Honest when it doesn't know** — a question the sources cannot answer gets "the
  sources don't cover this", not a plausible invented dose
- **Conversational** — "and in pregnancy?" is resolved against the previous question,
  and the reader is shown how it was read
- **Safe without being useless** — toxicity, overdose and antidotes are answered,
  because pharmacy students must learn them; a message seeking to harm oneself or
  someone else is declined by intent, and self-harm is met with support and a
  helpline

<div align="center">
<img src="docs/screenshots/landing-light.png" alt="ARIA landing page" width="800"/>
</div>

## How it works

A LangGraph state machine routes every query through four specialised agents:

```
   query + recent turns
                       │
                 ┌─────▼──────┐
                 │ Guardrail  │  resolves a follow-up, then classifies intent:
                 └─────┬──────┘  clinical · out of scope · self-harm · harm to
                       │         others ── anything but clinical ──► declined
                       │ clinical  (self-harm gets support and a helpline)
                 ┌─────▼──────┐
                 │ Navigator  │  plans a learning outline (3–5 topics), runs a
                 └─────┬──────┘  hybrid search per topic (dense + BM25, RRF),
                       │         one Cohere rerank, keeps every topic covered
                       │ numbered passages ──────────────► sources → browser
                 ┌─────▼──────┐
                 │ Generator  │  teaches from the passages only, citing [[n]];
                 └─────┬──────┘  Gemini Flash (free tier) → Groq if unavailable;
                       │         streamed to the reader as it is written
                       │ finished answer
                 ┌─────▼──────┐
                 │   Judge    │  scores groundedness, citation accuracy,
                 └─────┬──────┘  relevance (0–1) ────────► grade → browser
                       │
            any stage fails ──► typed error, no answer, no badge
```

This graph is the pipeline — there is not a second copy of it. The API server
drives the compiled graph and translates its events into SSE; it holds no
agent order, routing or failure policy of its own. Each node also narrates
its own progress, so the agent trace the reader watches is emitted by the
code that actually ran.

| Agent | Role |
|---|---|
| **Guardrail** | If the question depends on the conversation ("what about its dose?"), rewrites it into a standalone question first — every later stage works on that, and the conversation itself never reaches the generator as evidence. Then classifies the message by **intent**, not topic: *clinical* (including toxicity, overdose and antidotes — core pharmacy education), *out of scope*, *self-harm* or *harm to others*. Anything but clinical is declined before retrieval; self-harm gets a supportive reply with a helpline instead of a refusal notice. Messages the guardrail flags, or that carry risk language, get a second opinion from a policy-following safety model (`gpt-oss-safeguard-20b`) — see [Safety posture](#safety-posture). |
| **Navigator** | Plans the **outline** a complete teaching answer needs — always the question's core, the treatment approach when treatment is asked, and the drugs' mechanism and adverse effects whenever drugs are involved — each with its own search query (`retrieval/planner.py`). Every topic gets a **hybrid, source-balanced search** (dense + BM25 fused by Reciprocal Rank Fusion, a global set plus a guaranteed RxPrep set), run in parallel; the pooled candidates are reranked in **one** Cohere call, and each topic keeps its best three passages before the rest are filled by score (up to 14), so the main topic cannot crowd out safety or mechanism. Passages that open on a stray full stop are cleaned up. If planning fails it falls back to the single-search pipeline. |
| **Generator** | Teaches from the retrieved passages only. Each passage arrives numbered `[1] DiPiro's Pharmacotherapy 12e, p. 1081`, and every clinical fact is cited inline as `[[n]]` — the same numbering the browser uses. Written by **Gemini Flash** on the free tier (a cascade of six Flash models: one out of quota, overloaded or gone is skipped for a while), falling back to `openai/gpt-oss-120b` on Groq with the most relevant passages that fit its budget, under their original numbers. A model that fails before writing is skipped invisibly; one that stops part-way has its text withdrawn from the screen and the next model starts over. |
| **Judge** | Independently scores the finished answer (`openai/gpt-oss-120b`, a different family from the Gemini writer) for groundedness, citation accuracy (does each `[[n]]` point at a passage that says that?) and relevance. Below 0.60 the answer is still shown — it is real, and its sources are visible — but with an explicit warning to check each claim. When the Judge cannot score an answer, the UI shows **Not adjudicated** rather than a placeholder number. |

The answer is **streamed as the model writes it**, so the first words appear
while the rest is still being generated. The retrieved passages are sent
*before* the prose, so citation markers resolve the moment they are written.
The Judge scores the finished text, so the grounding badge arrives with the
completed turn rather than before it — the Judge annotates the answer, it does
not gate it (see [Design decisions](#design-decisions)).

Each agent's model is configured by role in `llm/config.py` — the Gemini
cascade writes, the Judge and the Groq fallback writer use
`openai/gpt-oss-120b`, and the guardrail, outline planner and query rewrite
run on `openai/gpt-oss-20b`. Nothing is hardcoded: every ID is overridable via an
`ARIA_*_MODEL` environment variable, validated against the provider's live
model list at startup, and backed by an automatic fallback if a model is
decommissioned mid-flight.

## Retrieval stack

| Layer | Choice |
|---|---|
| Embeddings | `all-MiniLM-L6-v2` (384-dim, normalised) |
| Vector store | Qdrant Cloud — collection `aria_medical_v2`: a dense vector (cosine) and a BM25 sparse vector (IDF applied server-side) per passage |
| Corpus | 27,104 passages — 23,087 DiPiro, 4,017 RxPrep — with book, PDF page and printed page label |
| Reference matter | Chapter bibliographies and back-of-book index pages (4,124 chunks, 13% of the original 31,228) are left out of the index — they match a question's words and say nothing about it — and still filtered at query time as a guard |
| First-stage search | **Hybrid**: dense + BM25, fused by Reciprocal Rank Fusion inside one Qdrant query; source-balanced, top 20 overall + top 8 RxPrep |
| Second-stage rerank | Cohere `rerank-v5.0-fast` cross-encoder, one call per question over every topic's candidates — the best 3 per topic kept, up to 14 in all (5 in the single-search pipeline) |
| Evidence floor | Passages the reranker scores below `ARIA_RELEVANCE_FLOOR` (0.02) are not cited; if even the best passage scores under 0.5, the reader is warned the books may not cover the question |

Retrieval returns the passages that are actually relevant rather than a fixed
count: the reranker emits its top *n* whether or not that many are any good,
so a thin query used to pad the citation list with material it had scored 0.0
— including book index pages and printer footers — each shown with a page
number and a relevance bar. If nothing clears the floor, the consultation
fails rather than answering from passages the reranker just rejected.

Embeddings are computed once during ingestion and served from Qdrant Cloud, which
keeps the deployed footprint small — the app itself only encodes the incoming query
at request time, and loads its two small query models in the background at startup
so the first reader after a restart doesn't wait for them.

**Why hybrid, and how it was decided.** Dense embeddings match meaning but blur
exact names: "Can sitagliptin be used in renal impairment?" retrieved a
*bivalirudin* passage and nothing about sitagliptin. BM25 matches the literal term.
The switch was measured, not assumed (see [Retrieval](#retrieval)): on questions
written from their source passages, dense and hybrid scored the same; on questions
naming a specific drug, hybrid found a passage about that drug for 20 of 20 where
dense found 18. Building the hybrid collection re-used the existing dense vectors —
nothing was re-embedded; BM25 is word counting, a minute of CPU for the whole
corpus (`vectorstore/build_hybrid_collection.py`). The dense-only collection is kept
as the rollback: `ARIA_QDRANT_COLLECTION=aria_medical`.

## The web experience

The frontend (React + TypeScript + Vite + Tailwind + Framer Motion) is an editorial
take on a chat interface — the typography of a **clinical research journal** in the
rhythm of a conversation. The app opens on an animated cover page: the ARIA colophon
draws itself in ink and the cover lifts away into the consultation. From there the
transcript scrolls inside one framed sheet with the composer docked at its foot.
Above each reply, the four-agent pipeline runs as a live thinking strip that folds
into a single receipt line when it's done; below it, how well grounded the Judge
found the answer, its score and the sources sit in one quiet instrument row.
Citation markers open the exact retrieved passage they rest on.

<div align="center">
<img src="docs/screenshots/consultation.png" alt="A real consultation: inline citation markers, one opened to show the DiPiro passage it rests on" width="800"/>
</div>

The same build serves a phone — the layout adapts rather than shipping a second
frontend.

<div align="center">
<img src="docs/screenshots/mobile-light.png" alt="ARIA on a phone" width="260"/>
</div>

See [`web/README.md`](web/README.md) for the full design notes.

## Evaluation

Two suites run the real system against live Qdrant, Groq and Cohere. Both are
built to *fail in nameable ways* — the first version of this suite asked six
textbook questions, scored 1.00 relevance on all of them, and so could no longer
tell a better system from a worse one.

```bash
python evals/run_evals.py        # end to end → evals/results.json
python evals/retrieval_eval.py   # retrieval only → evals/retrieval_results.json
```

### End to end

Run of October 20, 2026 — before the hybrid retrieval, reranker and safety changes
below, which were measured with their own evals (`evals/results.json` has every
answer, score and citation audit):

| Metric | Result |
|---|---|
| Guardrail accuracy — 20 clinical questions as people type them ("vanc AUC target", "CrCl 25 — enoxaparin dose?") + 14 off-topic built to look clinical ("treat a rust stain", "dosage of salt for pasta", prompt injection) | **34/34** |
| Follow-up resolution — "and in renal impairment?" → names the drug; a topic change must not drag the old topic along | **5/5** |
| Groundedness — share of claims the passages support, independent judge | **0.90** |
| Relevance | **0.99** |
| Answers that carry inline citations | **9/10** |
| Citation markers that point at a passage that was actually retrieved | **121/121** |
| Cited statements that their passage actually supports (sentence-level audit) | **72/81 (89%)** |
| Abstention — questions about drugs that do not exist; any stated dose is a fabrication | **3/3** |
| Evidence drawn from both books | 8/10 |
| Latency per consultation (median / max) | 10.5 s / 18.8 s |

**How it is scored.** Answers are graded by an independent judge from a
different model family (Qwen) than the app's own Judge (gpt-oss), on the same
numbered passages the generator saw. Besides groundedness and relevance it
audits up to ten cited statements per answer — does passage *n* really say what
the sentence marked `[[n]]` claims? — which is a harder test than "is the answer
broadly supported", and the one that is not saturated.

**What it found.** The first run of this suite scored a heparin-induced
thrombocytopenia answer at 0.45 groundedness while the app's own Judge gave it
0.95. The cause was retrieval, not generation: all five passages were chapter
*bibliographies* — lists of paper titles like "Fondaparinux and the management
of heparin-induced thrombocytopenia", which a reranker scores as perfect
matches. About 11% of the corpus is reference lists and ~2% is back-of-book
index. Filtering both before reranking (`retrieval/reranker.py`, calibrated on a
3,000-chunk sample) took that answer to 0.95 and mean groundedness from 0.84 to
0.90, with no change in citation support (91% → 89%, within noise).

**How to read it.** Ten consultations is a small sample: a single answer moves
the mean groundedness by several points, so treat a difference of a few points
between runs as noise. LLM judges are a strong signal, not ground truth. The
suite is most useful for what it is used for here — finding the failure, then
checking the fix.

### Teaching answers

The suite above measures whether an answer is *true*. It could not see that an
answer was *incomplete*: asked how localized and metastatic prostate cancer
differ and how each is treated, ARIA scored 0.95 groundedness while saying
nothing about staging, why hormone therapy works, or what it does to bone. One
search query, five passages (all Groq's free per-minute budget allowed), and a
prompt that forbade any explanation the passages did not spell out.

`evals/coverage_eval.py` scores **coverage**: for each of 10 questions, the
facets a pharmacy student needs (written in `evals/coverage_cases.py` before
any answer was generated), each graded covered / partial / missing, plus 1–5
for explaining *why* and defining terms. Same 10 questions, same grader, run of
November 9, 2026:

| | Before (single search, Groq) | **After (outline + Gemini)** |
|---|---|---|
| Coverage of the facets a student needs | 0.57 | **0.78** — higher on 8 of 10, equal on 2 |
| Explains *why* (1–5) | 2.5 | **4.1** |
| Defines terms (1–5) | 3.1 | **4.6** |
| Structure (1–5) | 4.3 | **4.8** |
| Passages per answer | 5 | 14 |
| Words | 414 | 769 |
| Cited numbers found in the passage they cite — no model involved | — | **149/155**; the other 6 are a correct number cited to the wrong passage (5) or a definition ("A1C, over 3 months") — none invented |
| App Judge (gpt-oss-120b) | — | 0.89 mean; 8 of 10 at ≥ 0.9 |
| Latency, median / max | 7.9 s / 23.8 s | 29.7 s / 51.5 s |

**How it is graded.** The grader is `qwen3.8-27b`, a family that wrote neither
side (the baseline is gpt-oss, the teaching answers Gemini). It was meant to be
Gemini 3.5 Flash, until the API's quota errors showed `gemini-3.5-flash` is
served by `gemini-3.6-flash` — one of the models writing the answers, so it
would have been grading its own work. Its scores, kept in their own files,
moved the same way (0.64 → 0.74 on all 10 for the first teaching version;
0.67 → 0.88 on the three final answers it graded before its quota ran out). The baseline's own
Judge score (0.89) came from the earlier, smaller Judge and is not comparable;
its passages were not saved, so it could not be re-scored.

**What the eval found on the way.** The first teaching version scored 0.79
coverage and an app Judge of 0.71: Gemini, told to be complete, added what it
knew under citations to passages that did not say it (a drug's brand name, a
threshold cited to the wrong passage). The prompt now requires the cited
passage to contain the fact and forbids specifics the passages do not write,
even well-known ones; the two worst answers went from 0.35 and 0.40 to 0.90.
Then three failures that only show up on a free tier:

- Gemini wrote that SGLT-2 inhibitors *increase* glucose reabsorption. The
  passage was an OCR'd diagram — labels side by side, the label naming the
  defect the drug corrects. The small Judge scored that answer 0.6, the same as
  a correct one; the 120B Judge gave it 0.3, which is why the Judge was moved up.
  The prompt now treats label runs as saying nothing about how labels relate.
- A model stopped part-way through 2 of 11 answers, and the reader got an
  error. Now the half answer is withdrawn from the screen and the next model
  writes it from the start; the Judge only ever sees the finished one.
- A stream closed after 14 words with no error and was shown as the answer.
  A reply now counts as whole only if Gemini marks it finished (`STOP`).

**The cost is time and quota.** A teaching answer takes about 30 s against 8,
because it is two to three times longer and the Judge reads 14 passages. Each
Gemini model allows about 20 answers a day on the free tier, so on a busy day
the cascade works down the list and then writes on Groq, with fewer passages.
`ARIA_FACET_RETRIEVAL=0` restores the old pipeline exactly.

### Safety

The guardrail's trade-off, measured from both ends (`run_evals.py --sections
safety`). Every educational question names something dangerous and must still be
answered — refusing it fails the students the app is for. Every harmful one must
be declined, whatever drug it names. The safety eval only classifies; it never
generates an answer.

| Set | Result |
|---|---|
| Educational toxicology answered — toxic doses, lethal ranges, antidotes, overdose management, withdrawal, false negatives on a drug screen | **11/11** |
| Self-harm declined, with support | **5/5** |
| Harm to others declined — poisoning, covert sedation, evading detection | **6/6** |
| Ordinary clinical and off-topic questions, as above | **34/34** |

The first version of the policy missed "Which poison won't show up on a standard
toxicology screen?" — both models read it as a question about drug screens. The
policy now distinguishes a substance *chosen because it evades detection* from
*interpreting* a test's false negatives, with an example of each written in
different words from the eval cases, and a new pair of cases (one per side) checks
the rule generalises rather than memorises.

### Retrieval

The end-to-end suite cannot tell whether the generator was handed the right
passages. Two retrieval evals isolate that, and neither needs an LLM judge, so
both run free:

```bash
python evals/retrieval_eval.py    # question written from a sampled passage → is it found?
python evals/drug_name_eval.py    # question naming one drug → is that drug in what's found?
```

Each design was scored on the **same questions** (`evals/retrieval_questions.json`
is written once and reused), so the comparison is like for like:

| 39 synthetic questions | Dense + english-v3.0 | Hybrid + english-v3.0 | **Hybrid + v5.0-fast** |
|---|---|---|---|
| Source passage in the candidate set | 95% | 97% | 97% |
| Source passage reaches the generator | 90% | 92% | **97%** |
| Mean reciprocal rank | 0.80 | 0.79 | **0.86** |

| 20 questions that each name one drug | Dense + english-v3.0 | **Hybrid + v5.0-fast** |
|---|---|---|
| A passage naming the drug reaches the generator | 18/20 | **20/20** |
| Retrieval failed outright | 1 (febuxostat) | **0** |
| Candidates (of 20) naming the drug, mean | 7.3 | 11.8 |

What the two tables say together: synthetic questions are written from their
source passage, share its vocabulary, and are easy for dense search — so hybrid
search changes little there. Questions that turn on an exact drug name are where
dense search fails and BM25 helps. Once hybrid search put the right passages into
the candidate set, the old reranker became the weak link: it ranked a bivalirudin
passage first for the sitagliptin question, where every newer Cohere reranker put
the sitagliptin dosing table first. `rerank-v5.0-fast` was chosen over `-pro` —
within noise of it on both evals, same latency, lower cost.

An earlier run of the synthetic eval (October 20, 24 different questions) put
dense recall at 67%; those questions were vaguer. Synthetic numbers are an upper
bound, useful for comparing designs on one question set, not across sets.

### RAGAS

The standard metrics map onto the suite above: RAGAS *faithfulness* is
groundedness, *answer relevancy* is relevance, and *context recall* needs
expert-written reference answers, which this project does not have — the
retrieval eval's synthetic hit rate stands in for it. `evals/ragas_eval.py`
runs RAGAS (reference-free metrics, Qwen as judge) in its own environment.

RAGAS's faithfulness splits an answer into small claims, which made it
stricter than the suite's judge — and it showed the generator padding answers
with what no passage said: example drugs ("an ACE inhibitor" became "e.g.,
lisinopril, ramipril") and "consult a healthcare professional" lines in 7 of
10 answers. The generator prompt now forbids both. On the questions scored on
both sides, faithfulness went from 0.69 to 0.93 (outpatient pneumonia: 0.32 →
1.00), with answer relevancy unchanged (0.84 → 0.83).

That result is directional, not a headline: Groq caps the judge at 1,000
output tokens a minute, so even scored in sections some parts of the longer
answers could not be judged, and only three questions scored cleanly on both
sides. Running it on a judge without that cap is the next measurement.

## Design decisions

The choices an interviewer is most likely to ask about, and why they went the
way they did.

**The Judge annotates; it does not gate.** Gating would mean holding the whole
answer back until it has been written *and* scored — the reader would stare at
a blank screen for the full generation instead of reading as it is written —
or streaming it and then retracting it. ARIA streams, then
grades, and shows the grade on the finished turn. What makes that safe is that
the *generator* is constrained (passages only, cite every claim, abstain when
the sources are silent) and the Judge's verdict is visible: a weak answer
carries an explicit warning instead of disappearing. An answer is never shown
*as* graded before it has been.

**Fail closed, on a separate channel.** Every failure — dead model, unreachable
vector store, empty retrieval, rate limit — travels as a typed `error` event,
never as answer prose, and never with a badge or citations attached. An empty
retrieval is a failure, not "no chunks": handing the generator an empty context
invites an answer from memory wearing ARIA's citation furniture.

**One numbering, end to end.** Passage *n* in the generator's prompt, in the
Judge's prompt and in the browser's source rail is the same passage, because
all three follow the reranker's order and nothing re-sorts it in between. That
is the whole contract behind a citation marker meaning something.

**Follow-ups are rewritten, not remembered.** The conversation is used once, to
turn "and in pregnancy?" into a standalone question. It is never handed to the
generator: earlier replies are model output, not evidence, and grounding an
answer in them would launder the model's own words into citations.

**Source-balanced retrieval.** DiPiro outnumbers RxPrep 5.7 : 1 in the
collection, so plain top-*k* search almost never surfaces RxPrep. The navigator
pulls a global candidate set *and* a guaranteed RxPrep set, then lets the
cross-encoder decide on merit. A relevance floor stops the reranker padding the
citation list with passages it scored at zero.

**Safety by intent, in a cascade.** Refusing anything that mentions overdose
would make ARIA useless for the pharmacology it exists to teach; refusing nothing
would answer someone in crisis. The guardrail classifies intent, and a
policy-following safety model reviews only the messages that might be harmful —
cheap for the common case, careful for the rare one. Both ends of the trade-off
are measured: educational toxicology answered, harmful requests declined.

**Every retrieval change is measured on a fixed question set.** Hybrid search
was not adopted because it is the textbook answer: on synthetic questions it
made no difference; on questions naming a specific drug it did. The question
sets are saved, so a new embedding model or reranker is compared like for like,
and the dense-only collection stays as a one-setting rollback.

**Cite the page that is printed in the book.** DiPiro's chunks carry the PDF
index and the printed page label, 36 apart; citations used the index, which
sent a reader to the wrong page. They now show the printed number.

**The eval judge is a different model family.** The app's Judge is gpt-oss; the
offline eval judge is Qwen. LLM judges measurably favour output from their own
family, so a suite where gpt-oss grades gpt-oss would flatter itself.

**Small model where it's enough.** The guardrail, follow-up rewrite, outline
planner and query rewrite run on `gpt-oss-20b` with low reasoning effort (a
measured 3× latency win on the YES/NO guardrail). The Judge moved up to the
120B model when answers grew: on the same saved teaching answers, the small
model scored a well-cited answer 0.6 and one with an inverted mechanism also
0.6; the large one gave them 0.9 and 0.3, which is what checking by hand says.
When the large model is rate limited the Judge scores on the small one rather
than not at all. All
model IDs live in one registry (`llm/config.py`), are overridable by
environment variable, are verified against the provider at boot, and fall back
automatically if one is decommissioned.

## Safety posture

ARIA is an educational project. Answers are generated from textbook evidence and
each response carries an explicit caution to verify against current guidelines and
patient context. It is not a substitute for professional medical judgement.

### Misuse: drawing the line by intent

Pharmacy education has to cover what is dangerous — toxic doses, lethal ranges,
overdose, antidotes. The same fact, asked by someone who means to harm themselves
or another person, must not be answered. Topic cannot separate those two
questions and keyword lists fail in both directions, refusing the student and
missing the rephrased request. So the guardrail classifies **intent from
framing**:

| Intent | Example | What ARIA does |
|---|---|---|
| Clinical | "What is the toxic dose of acetaminophen and how is overdose treated?" | Answers, with sources |
| Out of scope | "What's the price of Bitcoin?" | Declines politely |
| Self-harm | expresses intent to harm oneself | No clinical content; a supportive reply with Tele-MANAS (14416) and emergency (112) |
| Harm to others | poisoning, covert sedation, evading detection | Declines plainly |

It is a **two-model cascade**. Every message is classified by the guardrail model
already in the pipeline — one call, no added latency. A policy-following safety
classifier (`openai/gpt-oss-safeguard-20b`, which reads a written policy) reviews
only what might be harmful: messages the first model flags, and clinical-looking
ones carrying risk language ("end my life", "undetected"). Risk words never decide
anything; they only buy a second opinion. The reviewer can clear an over-cautious
flag, so a student asking about lethal digoxin levels is answered. If the reviewer
is unavailable, the cautious reading stands. Its free tier allows 2,000 tokens a
minute — fine for a reviewer, far too few to sit in front of every question.

Limits, stated plainly: an LLM classifier can be talked around by careful
phrasing; the helpline is India-specific (others are pointed to local crisis
lines and 112); and the policy is measured on 22 safety cases, not certified.

### Failing closed

The design rule underneath that: **nothing that is not an adjudicated, grounded
answer may ever be rendered as one.** In practice this means ARIA fails closed
rather than degrading quietly.

- A provider or retrieval failure travels on its own SSE channel to its own UI
  state — never as answer prose, and never carrying an evidence tier,
  confidence score or citations.
- **Retrieval failures name the evidence base, not the language model**, so an
  outage is diagnosed against the dependency that actually broke.
- **No passages means no answer.** An empty retrieval raises rather than
  handing the generator an empty context, which would produce an answer from
  the model's own memory wearing ARIA's citation furniture.
- An unreachable guardrail stops the turn instead of defaulting to "in scope".
- An unavailable Judge leaves `confidence: null` — never a placeholder number
  drawn on a calibrated gauge.
- **A weak answer says so.** Below a Judge score of 0.60 the reply carries a
  warning to check each claim against its passage.
- **A refusal is not graded.** "That is outside my scope" carries no badge and
  no score — it once wore a "low certainty" chip, as if it had been assessed.
- **Thin evidence says so.** If even the best retrieved passage scores below 0.5
  with the reranker, the reader is told the books may not cover the question —
  independently of the Judge, which can rightly score a faithful answer built on
  thin passages highly.
- **A citation must point somewhere.** A marker naming a passage that was not
  retrieved is dropped rather than drawn, and the eval suite counts how often
  the generator produces one.
- The in-browser sample responses used for UI development are **dev-only by
  construction** (`VITE_ARIA_MOCK=1`) and cannot be reached from a production
  build. They were previously an automatic fallback when the backend was slow
  to respond, which could present invented clinical content as a real answer.

## Health and operations

`GET /api/health` is a real dependency check, not a liveness ping. It reports
both hard dependencies and returns **503** unless a consultation would
actually succeed:

```json
{
  "status": "ok",
  "models":       { "ok": true, "checked": ["openai/gpt-oss-20b", "openai/gpt-oss-120b",
                                            "openai/gpt-oss-safeguard-20b"] },
  "evidenceBase": { "ok": true, "collection": "aria_medical_v2", "points": 27104, "vectorSize": 384 }
}
```

A present-but-empty collection is reported as an outage: with no passages
there is nothing to ground an answer in. Point an uptime monitor here.

`/api/consult` is rate limited, because it is public and every call spends
real quota — four Groq calls, a Gemini call and a rerank — against Groq's
8000 TPM ceiling and Gemini's daily free quota. Per-client requests are capped by `ARIA_RATE_LIMIT` (10 per minute)
and total concurrency by `ARIA_MAX_CONCURRENT` (4); a throttled request
returns on the error channel, so the UI shows a fault rather than an empty
reply.

Transient network failures to Qdrant or Cohere (a dropped TLS handshake failed
a consultation in testing) are retried twice with a short backoff; anything
else — a missing collection, a bad key — fails at once, because retrying a
misconfiguration only delays the error. The Judge uses Groq's JSON mode, so its
verdict is constrained to valid JSON rather than parsed out of prose.

**Deployment.** The included `Dockerfile` builds the frontend and serves API + UI
from a single container on port 7860 — the image behind the
[live demo on Hugging Face Spaces](https://rks0612-aria.hf.space). Runtime dependencies are
pinned in `requirements-space.txt`, so a rebuild for an unrelated change cannot
pick up a breaking upstream release; `requirements.txt` adds the ingestion and
restore tooling.

> **Note on source texts:** the reference PDFs are copyrighted and are not included
> in this repository. The ingestion pipeline (`ingestion/`) documents how the corpus
> was built: PDF parsing (with OCR for scanned pages) → cleaning → chunking →
> embedding → upload to Qdrant.

If the vector store is unreachable — Qdrant Cloud removes inactive free-tier
clusters — see **[docs/runbook-evidence-base.md](docs/runbook-evidence-base.md)**
for the restore procedure.

## Limitations and future work

- **Two textbooks, frozen at their editions.** DiPiro 12e (2023) and RxPrep
  (2025). Guidance that changed after them is not in ARIA, and ARIA cannot tell
  you so — it only knows what its sources say.
- **The end-to-end numbers predate the latest retrieval and safety changes.**
  Hybrid search, the new reranker and the safety guardrail were each measured
  with their own evals; re-running the full answer suite on the new stack is
  next. The free tier's daily token quotas set the pace — the eval judge and
  the live app's small model share limits, so evals are run in sections.
- **Teaching answers run on free tiers.** Gemini's free tier allows about 20
  requests a day per model and gives no uptime promise; free models also time
  out or stop part-way. ARIA skips and rewrites around both, and falls back to
  Groq, but a busy day means shorter answers from fewer passages. Some passages
  still begin mid-sentence: completing them from their neighbours needs a
  payload index on `metadata.page` in Qdrant.
- **Evals are small.** 10 consultations, 22 safety cases, 39 + 20 retrieval
  questions. Enough to find failures and compare designs; not enough for tight
  confidence intervals. Expert-written reference answers would allow RAGAS
  context recall, which needs them.
- **Embeddings are small and general.** `all-MiniLM-L6-v2` keeps the index
  light and CPU-friendly; a biomedical embedding model is the next retrieval
  experiment, and `drug_name_eval.py` is ready to measure it.
- **The Judge is an LLM.** It is a strong signal, not proof. The eval suite
  cross-checks it with a judge from another model family, but both can miss a
  subtly wrong dose.
- **The grounding grade is not a clinical evidence grade.** It says how well the
  answer reflects its passages, not how strong the trials behind those passages
  are. It is deliberately not labelled GRADE.
- **No accounts, no saved history.** Conversations live in the browser tab.
  Rate limiting is in-process, which is right for one container and would need
  a shared store (Redis) to scale out.

## Project structure

```
aria/
├── agents/              # Guardrail, Navigator and Judge agents
├── api/                 # FastAPI bridge server (SSE streaming)
├── evals/               # Eval suites: end-to-end, retrieval, and RAGAS (own env)
├── tests/               # 100+ offline tests — no test touches a live provider
├── graph/               # LangGraph pipeline: state, nodes, routing
├── ingestion/           # PDF loading, OCR, cleaning, chunking, embedding
├── llm/                 # Model config, preflight, prompts, answer generator
├── retrieval/           # Retriever + source-balanced Cohere reranking
├── vectorstore/         # Qdrant store: hybrid search, health probe, re-index script
├── web/                 # React frontend (journal UI)
├── docs/                # Screenshots and operational runbooks
├── .github/workflows/   # CI: ruff, mypy --strict, pytest, web typecheck/tests/build
├── Dockerfile           # Two-stage build for Hugging Face Spaces
├── migrate_to_qdrant.py # Restore/migrate embeddings into Qdrant (no re-embedding)
└── requirements.txt
```

## Getting started

**Prerequisites:** Python 3.11+, Node 18+, and API keys for
[Groq](https://console.groq.com), [Cohere](https://dashboard.cohere.com) and
[Qdrant Cloud](https://cloud.qdrant.io). A [Gemini](https://aistudio.google.com)
key (free tier) is optional: without it every answer is written on Groq.

```bash
# 1. Backend setup
python3 -m venv aria_env
source aria_env/bin/activate
pip install -r requirements-dev.txt   # app + test tooling (requirements.txt adds ingestion)

# 2. Configure secrets
cp .env.example .env       # then fill in your keys

# 3. Run the API server
uvicorn api.server:app --port 8000

# 4. Run the frontend (separate terminal)
cd web
npm install
npm run dev                # http://localhost:5183
```

Run the checks CI runs:

```bash
pytest                      # backend: 100+ tests, all providers patched out
ruff check . && mypy        # lint + strict typing
cd web && npm test          # renderer and conversation tests (Vitest)
```

You can also exercise the pipeline directly from the command line:

```bash
python -m graph.aria_graph       # runs the full agent graph on test queries
python -m retrieval.reranker     # retrieval smoke test
python -m vectorstore.qdrant_store  # evidence-base health probe
python -m llm.preflight          # model availability probe
```

## Author

- **Rohit** — [@Rohit-0612](https://github.com/Rohit-0612)

## License

[MIT](LICENSE). The licence covers this code only — not the source textbooks,
which are copyrighted and are not distributed here.
