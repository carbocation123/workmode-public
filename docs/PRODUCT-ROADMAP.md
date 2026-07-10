# Product roadmap

This file records accepted follow-up work that is intentionally outside the current desktop packaging change.

## Completed baseline: unified conversation timeline

- New messages, streamed text, and tool completion are followed automatically while the reader remains near the bottom.
- Upward scrolling pauses automatic following and exposes a `Back to latest` affordance.
- One tool invocation is rendered as one compact card whose status changes in place; parameters, output, and changed paths stay collapsed by default.

## Completed baseline: parallel web access

- `web_search` accepts 1–5 query variants and runs them concurrently with bounded workers and result counts.
- `web_fetch` reads 1–4 public text pages concurrently with redirect, content-type, response-size, and private-network protections.
- Both tools are loaded directly with the other required work tools; source text is explicitly treated as untrusted input.

## Rich literature-research workflow — design pending

The baseline tools deliberately stop short of a scholarly research pipeline. A later explicit workflow may add:

1. turn the research question into several query variants;
2. add end-to-end cancellation and a per-search budget;
3. prefer scholarly/primary sources and retain title, author, venue, year, DOI, URL, and retrieval time;
4. deduplicate by DOI, normalized title, and canonical URL;
5. separate source excerpts from model inference and produce traceable citations;
6. let the user inspect, select, and inject findings into the working context.

Provider selection beyond the current no-key baseline, credentials, rate limits, PDF/full-text access, and citation export format need a focused design before implementation.

## Sub-agents — design discussion required

Do not add autonomous sub-agents until these boundaries are agreed:

- which tools and project paths each child may access;
- maximum concurrency, token budget, time limit, and cancellation behavior;
- read-only versus editing roles;
- how simultaneous file edits are isolated or reconciled;
- what context is inherited and what result schema is returned;
- how responsibility, progress, and failures appear in the main conversation;
- whether delegation is model-decided, user-confirmed, or explicitly requested only.

The first useful candidate is a bounded read-only literature-review team. Code-editing agents should come later, after file-conflict and approval semantics are proven.
