# Docs owed: atomic-commit

> Derives from: EPIC `atomic-commit`; evidence/acceptance.md (the developer asked, 2026-11-13, for
> the caller-level explanation given at acceptance to be in the docs).

Decided at accept (2026-11-13): **docs are owed.** The EPIC changed a use case (saving several
aggregates) and user-facing behaviour (all-or-nothing commit, the limit, batch mode, the conflict
message). The how-to and the architecture page are current; what is missing is the explanation
a developer using the toolkit needs to reason about concurrent edits.

## Pages

| Page | Genre | What it adds | Reader |
|---|---|---|---|
| `howto/commits.adoc` (new, "How commits and conflicts work", in the nav under *Build an application*; the docs have no explanation section yet) | Explanation | Why one commit is all or nothing; the version token from the caller's side (`get` remembers it); the guard per change (replace/remove: still at the version read; add: absent); what a `Conflict` means and why the toolkit never retries for you; the size limit and why; batch mode as many all-or-nothing commits, not one; the two retry paths (same unit of work, fresh re-run) and when a re-run converges (stable part IRIs) | Developers using the toolkit |
| `howto/adopt.adoc` #transaction | How-to | A "handle a conflict" recipe: catch `Conflict`, re-read in a new unit of work, re-apply if the edit still makes sense, commit; show the new message text; link the explanation | Developers using the toolkit |
| `howto/adopt.adoc` #transaction-batches | How-to | The two retry paths side by side (same unit of work vs a fresh run), with a short example of each; link the explanation | Developers importing data |
| `questions.adoc` | Questions | "What happens when two people edit the same thing?" and "Why did my commit raise Conflict?", linking the explanation | Everyone |
| `architecture/data-flows.adoc` #commit | Explanation (maintainers) | Link to the new explanation for the caller's view; no other change | Maintainers |

## How it runs

The docs stage after #93 merges (accept → docs → archive): the lead loads `technical-writing`; one
writer drafts the pages above; a cold reader (a fresh agent given only the pages) tests the how-to
recipes; `make check-docs`, `make check-diagrams`; one PR into `develop` with the MEDIUM review
set's doc lens (L2 doc agreement). Then the archive.
