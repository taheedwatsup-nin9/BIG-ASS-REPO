# /learn — "Build Your Personal Knowledge Base With AI (Step by Step)" (Nick Saraev)

**Video:** https://youtu.be/LP7bfT4vOlo · **Channel:** Nick Saraev (runs LeftClick, an AI growth agency) · **Published:** 2026-10-18 · **Runtime:** ≈12 min [inference — last chapter starts 10:48] · **Status: FINAL (transcript-level) — studied 2026-10-22; verdicts PROPOSED for Taheed.**

## Source status

- **Transcript: OBTAINED.** YouTube's own timedtext track-list endpoint returned empty and the youtu.be page fetch failed from this VM (same egress pattern as the roadmap pass), but a full transcript was retrieved via YouTubeToTranscript (mirror of the video's own captions). Everything in column (a) below is from that transcript — paraphrased, with short quotes only where the wording matters.
- **Verified metadata** (from the video description, mirrored on technology-in-business.net): title, channel, the one-line summary — *"Quick walkthrough of my own personal knowledge base/second brain system (Engram)"* — the chapter list (below), and two funnels: Maker School (paid Skool community, "customer #1 guaranteed") and Maker Zero (free Skool community holding "all course resources" + a copy-paste prompt that rebuilds the system).
- **Not verified:** the Maker Zero rebuild prompt itself (behind a Skool join — no sign-up attempted). Saraev's performance claims (e.g. ~9/10 cost/latency drop from dropping embeddings) are his assertions from his own tests, not independently checked.

## Chapter map (verified)

| Time | Chapter |
|---|---|
| 0:00 | From Vannevar Bush's Vision to AI Slop |
| 0:53 | What a Personal Knowledge Base Does |
| 1:49 | Why Recency and Retrieval Matter |
| 5:15 | Building Reliable Data Pipelines |
| 7:09 | Summaries, Atoms, and Institutional Memory |
| 9:09 | Make Your Knowledge Base Searchable |
| 10:21 | Keep the System Fresh and Working |
| 10:48 | Origins, Resources, and Wrap-Up |

---

## 0. What a PKB is (0:00–1:49)

**(a) Content:** A personal knowledge base = *"a searchable pile of your own stuff plus AI looking that up before it answers you"* — i.e. retrieval-augmented generation, minus the hype. He opens by mocking "second brain" marketing ("AI slop… very easy to sell"), then defends the real thing: he runs his own on a business doing real monthly revenue. His system is called **Engram**: ~35,000–50,000 records holding his Git history, all of the company's Claude sessions, and his video transcripts.

**(b) Map to Taheed's stack:** This is a description of what Taheed already built. Supabase `brain_memory` (~3,486 rows) + MUZI's memory files + `brain_pull.py` for the agents = the same architecture: a store of his stuff, searched before answering. Engram's source list (Git history, Claude sessions, transcripts) maps to his repo (BIG-ASS-REPO), the Lenovo Claude lane, Hermes chats, and Grok chats.

**(c) Verdict: ADOPT as validation.** No new system to build — the video's value is as a checklist against the existing brain. The gaps it exposes are in the sections below.

## 1. Recency weighting + retrieval over context-dumping (1:49–5:15)

**(a) Content:** Two failure modes of "just dump everything into the context window": (1) the model treats all text as equally important, so a two-year-old price beats the current one with full confidence; (2) **context rot** — retrieval accuracy degrades as the window fills, and cost/latency explode. His fixes: **date-stamp every record at ingest; boost recent records, decay old ones ("recency weighting")**; and **retrieve, don't dump** — the model first runs a fast inference to pick a search term, searches the base (usually <0.5s), and only the handful of best matches get appended to the prompt. Periodically, Engram sweeps the base and deletes what's no longer valuable.

**(b) Map:** Half of this is already his: brain sync v2.4.1 does tombstoning ("checked 25 chat rows, 0 stale") — deletion of stale rows is handled. The missing half is **ranking**: nothing in the current retrieval (MUZI memory search, brain_pull) applies an explicit recency boost/decay, so a superseded fact and its replacement compete at equal weight unless a human curated MEMORY.md. His memory system handles this by hand (claims replace claims); the raw brain rows don't.

**(c) Verdict: ADAPT.** Add an explicit recency term to brain retrieval ranking rather than rebuilding anything: newer rows win ties, old rows decay unless re-reinforced. Small change to the pull/search layer, directly attacks the "confident stale answer" failure he hates most (verify outputs, not reports — stale data is how wrong outputs happen).

## 2. Data pipelines / connectors (5:15–7:09)

**(a) Content:** *"This step matters the most"* — a KB is only as good as its data. Pattern per source: define the source (email, website, leads, Slack, VoIP call transcripts — and **AI chat sessions**, which sit on your computer as plain text and are *"normally deleted after 30 days"*), write a small **connector** script that pulls **only what's new since the last run**, stamps it with the current date/time, and runs on a schedule (his email connector: every 15 min). Security note he states explicitly: connectors get **read-only access** (his Gmail connector uses the Gmail API read-only) — *"you don't want to give this thing write access because it'll have total control over your life."*

**(b) Map:** This is his brain sync, almost component-for-component: `import_hermes_v2.4.1` is an incremental connector (Hermes chats → brain_memory) with a last-run watermark, and the v1 failure (five weeks silently importing from a path that never existed) is exactly the failure this chapter warns about. Gaps against his pattern: (1) **the Lenovo Claude sessions are not a brain source** — Hermes chats are, Grok chats were read once by hand, but the Claude lane's session history (where a large share of current decisions happen) isn't piped in, and per the video those plaintext logs age out at ~30 days; (2) his other sources (Drive docs, board posts) enter the brain ad hoc, not via watermark connectors.

**(c) Verdict: ADOPT (two specific builds).** (i) A Claude-sessions connector on the Lenovo (plaintext session logs → brain, incremental, read-only) — the single highest-value missing source. (ii) Keep the read-only rule as doctrine for any new connector; it already matches his scoped-key posture.

## 3. Summaries + atoms: the enrichment pass (7:09–9:09)

**(a) Content:** Raw text is hard to search, so at ingest a **cheap model** (he uses Claude Haiku) writes metadata for every record: (1) a **short summary of the item, rephrased several ways, including the question someone would probably type to find it**; (2) **"atoms"** — exact error messages, exact fixes, commands that worked, and **decisions plus why they were made**. Atoms are the point: they convert a team's implicit decisions into explicit **institutional memory**. At query time the agent searches the summaries, and a summary hit points back to the full raw record.

**(b) Map:** Partially present, split across two places. MUZI's curated memory does this by hand (claims, decisions with reasons, AGENTS.md lessons = his atoms for errors/fixes). The raw brain (3,486 rows) gets **no enrichment pass** — rows go in as-is, so brain_pull searches raw text only. His stack also has the cheap model already, and it's better than Haiku for his doctrine: **dolphin3 on the Zeabur Ollama is free, local, and private** — an enrichment pass there costs $0 and sends nothing to a third-party API, where Saraev's version pays per record and ships company data to Anthropic.

**(c) Verdict: ADAPT.** Adopt the pattern, swap the model: a Dolphin-run enrichment job over new brain rows (summary + likely-question + atoms: errors, fixes, commands, decisions). This is the highest-leverage upgrade in the video for his setup — it makes the existing 3,486 rows (and everything after) searchable the way agents actually query. Fits the local-models doctrine exactly; Haiku does not.

## 4. Search: BM25, no embeddings (9:09–10:21)

**(a) Content:** His most contrarian claim: **you don't need vector embeddings at all.** Engram search is plain-text **BM25** (1990s term-frequency ranking). He says dropping the vector DB cut inference time and maintenance cost *"by like 9/10"*, and cites Boris Cherny (creator of Claude Code) saying plain search outperformed every other approach they tried. State-of-the-art systems combine methods, but for a personal KB, BM25 + a smart model choosing search terms is enough.

**(b) Map:** This collides head-on with a decision Taheed made **yesterday**: nomic-embed-text as the embedding model going forward (rule-stack decision, 2026-10-21). His current retrieval is already hybrid in practice — MUZI's memory search behaves like ranked text search, while the brain spec (PHASE2-SHARED-RETRIEVAL-SPEC) leans on embeddings. Saraev's claim is plausible for keyword-rich technical corpora (error messages, commands — exactly his atoms) and weak for paraphrase-heavy recall. It is also cheap to test: BM25 over the brain's summaries vs the current pull, same query set, compare hits.

**(c) Verdict: PARK the switch; PROPOSE a bake-off.** Do not rip out nomic-embed-text on a YouTube claim the day after standardizing on it. Do run the comparison once the §3 enrichment exists (BM25 works far better over summaries+atoms than over raw rows — the two ideas are a package). If BM25 ties or wins on his own queries, the embedding pipeline becomes optional weight; if it loses, the claim dies on evidence, his preferred way.

## 5. Keep it fresh (10:21–10:48) + origins/resources

**(a) Content:** A background script must constantly re-check that connectors still work — API keys rotate, permissions change, routes break, *"and then obviously all of it fails"* silently. Origins: Engram was adapted from a second-brain/injection-pipeline write-up by **Cohere**; his own A/B against his earlier RAG attempts "wasn't even close." Resources (rebuild prompt, curricula) are free in Maker Zero; Maker School is the paid upsell.

**(b) Map:** The freshness warning is his biography: brain sync v1 imported nothing for ~five weeks without anyone noticing, because nothing watched the watcher. v2.4.1's tombstone reporting helps, and the mesh watcher (2h) covers services — but there is no scheduled check whose only job is "did the brain actually gain rows / did each connector run since its watermark." The Cohere origin is a credibility point in the video's favor (an ingestion-pipeline design from a retrieval company, not a guru invention).

**(c) Verdict: ADOPT the freshness check** (a small scheduled verification: per-connector last-run + row-delta, report-only-on-violation — same shape as his PARA guards). **PARK the Skool funnels**: Maker Zero's free rebuild prompt is worth one look only if the §3 build needs a reference; Maker School is a purchase — study-don't-buy applies, and nothing in it is needed.

---

## Bottom line

Of the video's five load-bearing ideas: **adopt 2** (Claude-session connector before logs age out; connector freshness check), **adapt 2** (recency weighting in brain retrieval; summaries+atoms enrichment — run on local Dolphin instead of Haiku), **park 1** (BM25-replaces-embeddings — test it later as a bake-off, don't switch). The headline finding is recognition, not novelty: **Engram is the system Taheed already built** (brain_memory + connectors + shared retrieval) described back to him with three concrete upgrades and one testable heresy. Nothing here changes the build order; the enrichment pass (§3) is the one item worth promoting into the queue.

## Decisions / flags for Taheed

1. **Time-sensitive:** per the video, Claude/ChatGPT session files on the Lenovo are deleted after ~30 days. If the Claude-lane history is going into the brain, the connector (§2) shouldn't wait a month — the oldest sessions are the first to go.
2. **Doctrine tension to rule on eventually:** nomic-embed-text standardization (his 2026-10-21 decision) vs this video's BM25-only claim. Proposed resolution is evidence, not debate: the §4 bake-off after §3 lands.
3. **No spend, no sign-ups taken:** Maker Zero/Skool untouched; Haiku not used — the enrichment design assumes local Dolphin per his doctrine.
