# Round 4 brief (leader, 2026-11-03)

Read BRIEF-round3.md first (goal, decisions DEC-4/5/8, layers L0–L6, method, the end goal: a
coherent, easy-to-maintain ecosystem developers love). Round 3 is integrated in the Antora docs
under /home/lps/work/repos/rdf-persistence/docs/modules/ROOT/pages/architecture/soa/
(index.adoc integrated findings, building-blocks.adoc, variants.adoc — system variants V1–V5 and
development approaches A–C —, catalogue.adoc, feature-taxonomy.adoc **v3**, libraries/, angles/).
Read index.adoc, building-blocks.adoc and variants.adoc before starting.

## Round 4 tasks for EXISTING analysts (append `## Round 4` to the END of your own raw report(s))
(a) **v3 cross-check** — every feature in the "v3 features" section of feature-taxonomy.adoc:
    Id | present / partial / absent / n.a. | evidence (file:line, GitNexus finding, or doc URL).
    Confirm absences with grep/GitNexus. Use the "Id mapping" appendix to relate to your own
    round-3 proposals.
(b) **Purpose and origin** (`### Purpose and origin`): what each tool was built FOR, who built it
    in which context, its design angle, and therefore where it could fit in L0–L6 and in the
    variants V1–V5 — or why it does not fit (see RUBRIC.md).
(c) **Variant fit**: for each of your candidates, which variants (V1–V5) and development
    approaches (A–C) it supports, enables, or blocks, in one table.
(d) **Corrections**: anything in the integrated docs pages that your evidence contradicts.
(e) Proposed new features (round 4), if any, with a proposed id in an existing area.
Angle analysts: also use the GitNexus indexes that were still building in round 3 (fluree-db,
api-platform-core) to confirm or correct the code claims you made from reading source.

## Report back (≤8 lines)
v3 counts, variant-fit headline, corrections to the docs, new features.
