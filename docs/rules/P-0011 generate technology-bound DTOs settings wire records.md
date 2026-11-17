---
kind: rule
id: P-0011
type: constraint
strength: hard
status: active
scope:
  - activity:coding
when: adding or changing a model
do: generate technology-bound DTOs (settings, wire records, template parameters, log context) from technical schemas into the layer that owns the technology, apart from the domain models; the domain layer never imports them
because: the split shows at once which classes are technology-bound DTOs and which are the domain's classes and objects
source: 2026-11-17 'we must separate teh technism ald teh domain models, that is important because then we trully see what are the DTOs that are technology bound, and what are teh domain classes and objects'
added: 2026-11-17
approved: 2026-11-17
last_confirmed: 2026-11-17
private: false
---
