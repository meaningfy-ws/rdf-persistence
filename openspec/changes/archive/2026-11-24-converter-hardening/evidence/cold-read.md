# Cold read: task 1.8 (2026-11-24)

Pages: `howto/uml-to-linkml.adoc`, `user-manual/serve.adoc`. Goal given to the reader: from a
`.qea` that draws classes, roles and a workflow, convert, generate and start a toy service.
Each reader was a fresh agent that had never seen the project.

| Read | Scope | Reached | Open questions |
|---|---|---|---|
| 1 | the two pages only | step 6 (composition root), blocked on real adapters | 11 |
| 2 | the two pages and their xrefs, after one fix pass (`37b89172`) | an in-process toy service on the testkit fakes | 11 |

Read 1's gaps in the two pages (file names, `rules=`, `--package` reference, `migrations`
folder, role level, `creator_role`, a toy service's adapters, serving `app`) were fixed in
`37b89172`.

Read 2's gaps are about onboarding a whole toy service, not the converter: project layout, the
minimum model, a complete toy `ServiceSettings`, a token outside a test, live server versus
in-process client. Two were contradictions between pages (`review` versus `loan` workflow,
`rules=` in `test.adoc`), fixed in this PR.

**Verdict: partly met.** Owner's decision (2026-11-24, D-3): fix the two contradictions here and
file the rest as a tutorial, #344.
