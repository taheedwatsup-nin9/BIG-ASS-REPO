# /learn — "Complete Guide to building an AI Second Brain with Claude" (Ray Fu)

**Video:** https://youtu.be/-SsAwIkW9rI · **Channel:** Ray Fu (@raycfu — ex-Meta senior engineer, AI automation educator) · **Status: FINAL (companion-guide level) — verdicts are PROPOSED. Sent by Taheed 2026-10-22 23:29 with no caption, followed by his open question "Discuss how we can get better" — the mapping below is weighted toward how MUZI and the agent team operate better.**

## Source status (read this first)

- **Transcript: NOT obtained.** Attempts, all logged: direct watch-page fetch via curl hit YouTube's bot-check interstitial; the `api/timedtext` track list and English track endpoints returned empty; the youtubei player API (Android and iOS clients) returned HTTP 400 "Precondition check failed"; three Invidious instances returned 403 / 301 / endpoint-disabled; one transcript-mirror service returned HTTP 429 (rate limit — hard stop, not retried). **No spoken content is quoted or paraphrased anywhere below.**
- **Identity: VERIFIED** via YouTube oEmbed + the watch page's extracted text: title "Complete Guide to building an AI Second Brain with Claude," author Ray Fu. **Publish date and runtime: NOT obtained** — no reachable source exposed them (oEmbed doesn't carry them; the player API was blocked). Not guessed.
- **What IS verified about the content, two sources:**
  1. The video's own description: *"In this video, I show you the exact way to build out an AI second brain with Claude and Obsidian… This guide is for everyone so you can follow along even if you are a complete beginner!"* It links his free guides "including one on building the Claude second brain" (raycfu.com), his Skool community, and a comment-gated Claude/ChatGPT Max subscription giveaway.
  2. **The companion written guide** — "How to Build an AI Second Brain with Claude and Obsidian" (raycfu.com/guides/claude-obsidian-ai-second-brain), fetched in full 2026-10-22. This is the creator's own written version of the same build the video teaches (the description points viewers to it). Everything in the "system" section below is verified *from the guide*, and is the strongest available proxy for the video — but it is the guide's text, not the video's transcript. If the transcript is ever pulled (Lenovo browser), re-check emphasis and any video-only steps.
- The guide itself is a presentation of **Andrej Karpathy's "LLM Wiki" pattern** (his gist is linked and quoted at length inside the guide). Credit where due: the architecture is Karpathy's; Ray Fu's contribution is packaging it as a beginner build with exact prompts and automations.

## The system (verified from the companion guide)

**Core idea — compile, don't retrieve.** Standard RAG re-derives knowledge from raw chunks on every question; nothing accumulates. Instead, the LLM incrementally builds and maintains a **persistent wiki** — interlinked markdown pages sitting between you and your raw sources. Each new source is read once, integrated into existing pages, with contradictions flagged and the synthesis revised. The wiki compounds; the human sources, explores, and asks — the AI does all summarizing, cross-referencing, filing, and bookkeeping.

**Three layers:**
1. **raw-sources/** — an unorganized dump (articles, transcripts, notes, screenshots). **Immutable**: the AI reads, never modifies. Source of truth.
2. **wiki/** — AI-owned summaries, concept pages, entity pages, comparisons, synthesis. The human reads; never hand-edits. Two special files:
   - **index.md** — a catalog of every page with a one-line summary, updated on every ingest. Queries read the index first, then drill in — the guide claims this works well to hundreds of pages with **no embedding/RAG infrastructure**.
   - **log.md** — append-only chronological record (ingests, queries, health checks) with consistent `## [date] type | title` prefixes so it's greppable.
3. **Schema file** — `CLAUDE.md` (or `AGENTS.md`) in the vault root holding Karpathy's LLM Wiki prompt: structure, conventions, workflows. "The key configuration file… what makes the AI a disciplined wiki maintainer rather than a generic chatbot." Human and AI **co-evolve** it over time.

**Tools:** exactly two — Obsidian (browse/graph view) and Claude Code (the agent). Build is a one-shot prompt: read everything in raw-sources, compile the wiki, index first, log everything.

**The three daily operations:**
- **Ingest** — drop a source in raw-sources, run the ingest prompt (summary page + index update + update every connected concept page + log entry + *"Show me every file you touched"*). One source can touch 10–15 pages; contradictions with existing knowledge get surfaced.
- **Query** — ask against the wiki (answers carry citations); **save good answers back into the wiki as new pages** so exploration compounds instead of dying in chat history.
- **Lint** — a weekly health check with an exact prompt: find contradictions between pages, orphan pages with no inbound links, concepts mentioned repeatedly with no page of their own, and claims outdated by newer raw sources → `lint-report.md` with specific fixes. Framed as quality control: an early AI error, saved back uncritically, compounds into later answers.

**Automations (Step 6):** a morning briefing (script + cron: open actions due today from Memory.md + new raw sources in the last 24 h → briefing) and a call-transcript processor (decisions → decision-log.md, actions → action-tracker.md, topic page created). Optional tooling named: Obsidian Web Clipper (capture), Dataview (frontmatter queries), git under the vault ("version history, branching, and collaboration for free"), and **qmd** (github.com/tobi/qmd — a local markdown search engine: hybrid BM25/vector + LLM re-ranking, on-device, with a CLI and an **MCP server**).

**The guide's own closing caveat, verbatim in substance:** *"You do not need Obsidian to make this work. A folder of markdown files and a good schema file will outperform a fancy tool stack 90% of the time."*

---

## Mapping to Taheed's stack — and how the team gets better

The headline finding: **Taheed already runs this architecture, one generation further along.** Supabase `brain_memory` (3,486 rows) with the nightly Hermes import (tombstoning, source-scoped deletes) is the compiled-knowledge layer; `MEMORY.md` + people/groups pages + their `INDEX.md` files are the index-first wiki; daily logs are `log.md`; `ALIGNMENT_SYNTHESIS.md` is a maintained synthesis page; AGENTS.md/SOUL.md + the pending RULES.md consolidation are the schema file. Tonight's *other* video (Nick Saraev's PKB/Engram study) converged on the same pressure points from a different direction: connector freshness, recency/decay, hybrid retrieval. Two independent sources in one night pointing at brain health is a signal, not a coincidence. The upgrades below are where the video genuinely adds something he doesn't already do:

### 1. The Lint pass — the single biggest transferable upgrade
**(a)** A scheduled, explicit health check over the knowledge base: contradictions, stale/superseded claims, orphans, missing pages — written as a report with specific fixes.
**(b)** Nothing in his stack does this today. PARA guards were *proposed* (report-only-on-violation) but never built; the rule-stack audit found 33 inconsistencies by hand; and this very night produced a live example — a session-ledger row marked VERIFIED whose cited proof file wasn't in the repo, caught only because a verifier happened to check. A weekly lint over the memory tree + brain + session ledger, report-only, findings surfaced to Taheed, never auto-editing, is the Karpathy QC loop his system lacks. It also operationalizes his own doctrine: verify outputs, not reports — on a schedule instead of by luck.
**(c) Verdict: ADOPT (build).** Highest-value item in this study. Small, cheap, fits the cron fleet he already runs.

### 2. File good answers back — close the compounding loop
**(a)** Analyses and comparisons generated in chat get filed into the wiki as pages, so each question improves the next answer.
**(b)** Partially live: /learn studies land as files, audits land in mesh-ops, but retrieval of those artifacts into every agent's hands is the unfinished Phase 2 (per-agent pull-on-start wiring still pending; the studies mostly serve the session that made them). The discipline to add is deliberate: every study/audit ends with a brain ingest + an index line, not just a file in a folder.
**(c) Verdict: ADAPT.** No new system — a closing step added to existing study/audit workflows, tied to the Phase 2 retrieval work already specced.

### 3. Immutable raw sources — formalize what imports already assume
**(a)** Raw inputs are read-only forever; all synthesis lives in the derived layer, so any wiki page can be re-derived and audited against its source.
**(b)** His daily logs and chat imports already behave this way informally. It becomes a live decision via the Gemini→Obsidian import goal (~¾ done): its premise was the Obsidian app he no longer has. Retargeted through this lens, the import's output belongs in an immutable raw-sources home feeding the brain — not in an app. The pattern strengthens the retarget option and weakens "finish it as originally designed."
**(c) Verdict: ADAPT** — and it feeds a decision already on his desk (see below).

### 4. Index-first retrieval, and qmd
**(a)** The guide claims a maintained index beats embedding infrastructure to hundreds of pages; at larger scale it names qmd — local, hybrid BM25/vector, LLM re-ranking, MCP-native.
**(b)** His people/groups INDEX.md files already prove index-first works at his scale for the file side; the brain side is embeddings (nomic-embed-text, standardized 2026-10-21 *by his decision*). Replacing that wholesale on a video's say-so would re-litigate a settled standard. But qmd lands exactly on the open question from tonight's Saraev study — the proposed BM25-vs-embeddings bake-off — and it's the *kind* of hand he likes: local, free, on-device, MCP-exposed (his MCP server POC is the natural host), and his standing rule covers it: downloaded hands get vetted before wiring.
**(c) Verdict: PARK the index-replaces-embeddings claim; ADAPT qmd into the already-proposed retrieval bake-off** as the markdown-side candidate. One trial, measured, against the current standard — not a switch.

### 5. Schema co-evolution — validation, not new work
**(a)** The schema file is the discipline layer, refined by human + AI as the domain teaches them.
**(b)** This is his AGENTS.md + SOUL.md + RULES.md consolidation, already designed (migration spec drafted; four decisions pending with him). The video adds nothing except independent confirmation that the schema file is "the most important step" — which his stack already treats it as.
**(c) Verdict: ADOPT as validation.** No action beyond what's queued; cite it when the RULES.md decisions come back around.

### 6. The automations (morning briefing, transcript processor)
**(a)** Cron-driven morning digest from the brain; every call transcript mined into a decision log + action tracker.
**(b)** Briefing: his Feed + heartbeat + goal briefings already occupy this slot — building Ray Fu's version would duplicate. Transcript processing: maps onto his meeting-follow-up skill and tracked-items system (decisions/actions filed to durable homes) — the pattern is already his; the one borrowable sharpening is the guide's insistence that *nothing* stays only in chat history, which is item 2 above.
**(c) Verdict: PARK the briefing as a duplicate; ADAPT the transcript discipline into item 2.**

### 7. Obsidian itself
**(a)** The video's browsing layer: vault, graph view, Web Clipper, Dataview.
**(b)** He deleted the app (2026-10-22: "Obsidian I don't even have the app anymore"); his user-facing surfaces are the BAC viewer and the planned Drive portal. The guide's own closing line concedes the app is "just a nice window" — the system is folders + schema + AI, all of which he has in other materials. Graph-view orphan detection is the only real loss, and item 1's lint pass covers it programmatically.
**(c) Verdict: PARK.** Do not reinstall an app he deliberately dropped to chase a video's screenshot.

### 8. The funnel (Skool, giveaway, $9.99 playbook, $299 consults)
**(a)** The video is top-of-funnel for a paid community and services.
**(b)** Same shape as Boost OS: the *content* is the value; the purchase is a separate, unmade decision. Study-and-adopt applies.
**(c) Verdict: PARK (do not buy).** Nothing here needs his money.

---

## Decisions for Taheed

1. **Obsidian verdict (already leaning, now load-bearing):** confirm the app stays out. That single call settles the Gemini→Obsidian import goal — retarget its output to an immutable raw-sources home feeding the brain, or kill the goal. The video doesn't change his stack either way; it just removes the last reason to keep the question open.
2. **Queue position for two small builds** — the weekly brain **lint pass** (item 1) and the **qmd trial** inside the retrieval bake-off (item 4). Both are MUZI-side, both cheap, both compete for the same hours as the Dec 31 CR8MOR build order. His call on whether they jump the queue or wait.
3. **Nothing to buy.** The guide is free, the tools are free, the community is not needed. (Standing rule: MUZI doesn't spend; flagging because the video's design pushes toward the Skool door.)

## Bottom line

Ray Fu is teaching beginners to build, from zero, a single-user version of what Taheed already operates as a multi-agent system. The video changes no architecture and no build order. Its real contribution is two disciplines his stack designed but hasn't finished: **a scheduled lint pass that hunts contradictions and stale claims before they compound**, and **filing answers back so work products compound instead of evaporating**. Adopt those two, trial qmd inside the existing retrieval question, let the rest validate the direction — and let the Obsidian question close.
