# Product roadmap

This file records accepted follow-up work that is intentionally outside the current desktop packaging change.

## Unified conversation timeline pass

- Automatically follow new messages, streamed text, and tool completion while the reader is already near the bottom.
- If the reader scrolls upward, pause automatic following and show a `Back to latest` affordance.
- Represent one tool invocation as one compact card whose status changes from running to completed/failed in place.
- Keep parameters, output, and changed paths collapsed by default; do not render separate start/result bubbles.

## Literature-research web search

Search should be an explicit research workflow rather than an always-loaded general web tool:

1. turn the research question into several query variants;
2. execute those queries concurrently with cancellation and a per-search budget;
3. prefer scholarly/primary sources and retain title, author, venue, year, DOI, URL, and retrieval time;
4. deduplicate by DOI, normalized title, and canonical URL;
5. separate source excerpts from model inference and produce traceable citations;
6. let the user inspect, select, and inject findings into the working context.

Provider selection, credentials, rate limits, PDF/full-text access, and citation export format need a focused design before implementation.

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
