# Runbook — restoring ARIA's evidence base

**Symptom:** every consultation fails at the Navigator step. The UI shows
*"the reference library is currently unreachable"*. `/api/health` returns
**503** with `evidenceBase.ok: false`.

**Cause:** ARIA's Qdrant cluster is gone or unreachable. Qdrant Cloud's free
tier removes clusters after a period of inactivity, and a removed cluster's
hostname keeps resolving — `*.cloud.qdrant.io` is a wildcard DNS record — so
the address looks alive while the TLS connection is refused.

Retrieval is a hard dependency. Without source passages ARIA fails the turn
rather than answering from the model's own memory, so this is a total outage,
not a degradation.

---

## 1. Confirm it is the evidence base

```bash
curl -s https://<your-space>.hf.space/api/health | python3 -m json.tool
```

`models.ok: true` with `evidenceBase.ok: false` means the LLM provider is
healthy and only the vector store is down. Locally:

```bash
python -m vectorstore.qdrant_store
```

To tell a removed cluster apart from a network problem, check whether a
made-up cluster ID resolves to the same addresses. If it does, DNS is a
wildcard and proves nothing about the cluster:

```bash
dig +short <your-cluster-id>.<region>.aws.cloud.qdrant.io
dig +short doesnotexist-0000.<region>.aws.cloud.qdrant.io
```

## 2. Create a replacement cluster

In the [Qdrant Cloud console](https://cloud.qdrant.io): create a free cluster,
then generate an API key for it. Put both in `.env`:

```
QDRANT_URL=https://<new-cluster-id>.<region>.aws.cloud.qdrant.io
QDRANT_API_KEY=<new key>
```

## 3. Restore the vectors

Restore from the ChromaDB snapshot (`aria_chroma_db_backup.tar.gz`). This
re-uploads existing vectors — it does **not** re-embed, and does not need the
source PDFs, so it takes minutes rather than hours:

```bash
tar -xzf ~/Desktop/aria_chroma_db_backup.tar.gz -C vectorstore/
python migrate_to_qdrant.py
```

The script is idempotent: point IDs are derived deterministically, so a run
that is interrupted can simply be repeated.

Expected result — **31,228 points, 384 dimensions, both books**:

```
  points      : 31228
  vector size : 384
  RxPrep      : 4181
  DiPiro      : 27047
```

If `RxPrep` is 0 the source-balanced retriever silently degrades to a
single-book system, and the RxPrep half of the corpus needs re-ingesting
(`ingestion/ingest_rxprep.py`).

To check an existing collection without uploading:

```bash
python migrate_to_qdrant.py --verify-only
```

## 4. Point the deployment at it

On the Hugging Face Space → **Settings → Variables and secrets**, update
`QDRANT_URL` and `QDRANT_API_KEY`, then **Restart this Space**.

## 5. Verify

```bash
curl -s https://<your-space>.hf.space/api/health | python3 -m json.tool
```

`status: "ok"` and `evidenceBase.points: 31228`. Then ask a real clinical
question through the UI and confirm citations appear in the margin.

---

## Preventing a silent recurrence

- **`/api/health` is now a real dependency check.** It probes the collection
  on every request and returns 503 unless the store is reachable, present and
  non-empty. An empty collection counts as an outage: it cannot ground an
  answer. Point an uptime monitor at this endpoint — the previous version
  reported `ok` for as long as the models existed, which is why this outage
  went unnoticed.
- **Keep the snapshot current.** `aria_chroma_db_backup.tar.gz` is the only
  copy of the embeddings outside Qdrant. Re-export it after any ingestion run;
  without it, recovery means re-OCRing ~1 GB of PDFs.
- **Free clusters lapse.** Either keep the Space warm enough to count as
  activity, or plan on this runbook.
