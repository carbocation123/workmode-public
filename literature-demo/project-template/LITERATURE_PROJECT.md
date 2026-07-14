# Literature library collaboration protocol

This is a specialized Workmode literature-library project. The project folder is the
source of truth; the literature interface is a projection of these files. Formal
Workmode sessions, JSONL tool events, context budgeting, compaction and cancellation
remain the conversation kernel.

## Fixed structure

- `catalog.json`: authoritative paper records and project-relative paths.
- `tags.json`: the semi-open tag registry. Paper records store tag IDs.
- `papers/unprocessed/pdf/`: imported PDFs awaiting discussion or archival checks.
- `papers/unprocessed/extracted/<paper-id>/`: MinerU text, layout, images and facts.
- `papers/processed/`: archived PDF and extraction trees.
- `notes/*.md`: project notes that may be searched and discussed.
- `exports/`: generated Markdown or PDF note exports.

Do not create parallel catalogs, hidden metadata stores or extra root directories.

## Tool boundary

Only literature-domain tools are available in this mode. There is no shell, Python,
generic file editor, web search, generic memory tool or plan tool. A literature tool
call is an executable request: it does not require a second proposal/approval tool or
a `confirmed` boolean. The backend still validates the project root, paper IDs, fixed
paths, JSON schemas and atomic writes.

The papers or notes selected in the interface are current context, like an editor's
current file. Selection is never permission. A domain tool may operate on any real
paper ID in the current project.

Before assigning or replacing paper tags, call `literature_tag_list` and inspect the
canonical registry. Reuse existing names or aliases whenever possible; create a new
provisional tag only when no existing tag expresses the same concept.

## Evidence discipline

Facts, numeric values, phenomena and author claims must keep their source locations.
Objective fact reports contain source facts only. Cross-paper interpretation belongs
in the explicit cross-literature section or project notes and must not masquerade as
paper facts. Metadata comes from the PDF first page `Cite This` line, with existing
`layout.json` header blocks as fallback; do not infer it from filenames or search
snippets.
