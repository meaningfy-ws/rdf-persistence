## P-0007 (P-0007 propose fewer concepts and links that.md)

---
kind: rule
id: P-0007
type: preference
strength: default
status: active
scope:
  - activity:modelling
when: asked to make a model more elegant, crisper or simpler
do: propose fewer concepts and links that still satisfy every requirement
instead_of: adding classes, properties or associations in the name of elegance
because: the owner wants a smaller crisp model, never a larger one, and never at the cost of a requirement
source: "2026-11-12, owner: 'when I asked for a more elegant model I asked for a smaller crisp model, not larger and more complex one'; 'it is indeed like this but making sure of course that the requirements still can be satisfied'"
added: 2026-11-12
approved: 2026-11-12
last_confirmed: 2026-11-12
private: false
---

## P-0008 (P-0008 draw a dependency from the class.md)

---
kind: rule
id: P-0008
type: preference
strength: default
status: active
scope:
  - activity:modelling
when: a class links to a controlled list (enumeration) in a UML model
do: draw a dependency from the class to the enumeration, named by the property, not an attribute typed by the enumeration
instead_of: an attribute whose range is the enumeration
because: the SEMIC style guide connects classes to controlled lists this way
source: "2026-11-19: 'the links between the classes and controlled lists in SEMIC styleguide are connected with dependency from class to the controlledList/Enum (and not as attributes pointing to that enum as range)'"
added: 2026-11-19
approved: 2026-11-19
last_confirmed: 2026-11-19
private: false
---

## P-0009 (P-0009 store anything that is or can.md)

---
kind: rule
id: P-0009
type: constraint
strength: default
status: active
scope:
  - activity:modelling
when: deciding where MWB2 stores content
do: store anything that is or can be RDF in the triple store as data; keep only non-RDF content as files (blobs)
because: results and models must be queryable as data, not buried in files
source: "2026-11-19: 'anything that can be data/rdf shall be in the triple store not in the files'"
added: 2026-11-19
approved: 2026-11-19
last_confirmed: 2026-11-19
private: false
---

## P-0011 (P-0011 draw the domain classes only bring.md)

---
kind: rule
id: P-0011
type: constraint
strength: default
status: active
scope:
  - activity:modelling
when: drawing the domain model in EA (or any UML source the toolkit converts)
do: draw the domain classes only; bring the toolkit's classes in through the conversion (defaults and tagged values)
instead_of: drawing toolkit classes and generalisations to them
because: the model must focus on the domain; the toolkit integrates everything else
source: "2026-11-20, owner: 'i would evens kip the tookit classes, if we do nto need them, we must focus on teh domain classes mainly the toolkit of course brings in everythign else, and integrates it into teh domain model'"
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---

## P-0012 (P-0012 state each fact once and integrate.md)

---
kind: rule
id: P-0012
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: modelling
do: "state each fact once and integrate concepts properly: no association repeating another in reverse, no attribute repeating a slot the toolkit gives"
because: the model must be consistent and non-redundant
source: "2026-11-20, owner: 'the model must be consistent and non-redundant, so a proprt integration of concepts is a must'"
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---

## P-0013 (P-0013 show the diagrams generated from the.md)

---
kind: rule
id: P-0013
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: a model is turned into LinkML
do: show the diagrams generated from the LinkML for inspection and in the documentation for consultation
instead_of: hand-drawn or EA-exported diagrams as the reference
because: what is inspected and consulted must be what is generated
source: "2026-11-20, owner: '(then a clear modl diagrams generated from link ml are a must and shown for inspection,a nd for documentation for consultation)'"
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---

## P-0014 (P-0014 adjust the architecture docs model page.md)

---
kind: rule
id: P-0014
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: the model changes
do: adjust the architecture docs (model page, glossary, ADRs) to the model in the same change
because: the docs must follow the model
source: "2026-11-20, owner: 'the architecture docs must be adjusted according to the model.'"
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---

## P-0016 (P-0016 draw them in EA on top.md)

---
kind: rule
id: P-0016
type: preference
strength: default
status: active
scope:
  - activity:modelling
when: modelling MWB2's access and workflows
do: "draw them in EA on top of the toolkit's concepts: subclass the toolkit class, or draw its data as instances or a state machine; never only hand-written LinkML or YAML"
because: the owner wants the whole model, access and workflows included, in one source that extends rdf-persistence
source: 2026-11-21 'we have to somehow model the access inside the eapx, and have conventions to extend the constructs from the rdf-persistence for access; the same is true for a series of workflows and state transitions'
added: 2026-11-21
approved: 2026-11-21
last_confirmed: 2026-11-21
private: false
---

## P-0017 (P-0017 keep it in small thematic packages.md)

---
kind: rule
id: P-0017
type: preference
strength: default
status: active
scope:
  - activity:modelling
when: organising the EA model
do: keep it in small thematic packages, one per converted module, re-shuffled when a package mixes themes
because: the owner wants small thematic modules for better maintenance
source: 2026-11-21 'the final linkml model shall be broken in small thematic submodules, for better mainenance'
added: 2026-11-21
approved: 2026-11-21
last_confirmed: 2026-11-21
private: false
---

## P-0026 (P-0026 check every term and its namespace.md)

---
kind: rule
id: P-0026
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: modelling with terms of an external vocabulary (RML, R2RML, SKOS, …)
do: check every term and its namespace against the published specification before proposing or applying it
because: the EA model mixed RML-Core and legacy RML names unnoticed
source: "2026-11-27: 'check again that the terms are correct and belong to the right vocabulary! Lookup the RML specifications'"
added: 2026-11-27
approved: 2026-11-27
last_confirmed: 2026-11-27
private: false
---

## P-0027 (P-0027 start from the latest qea on.md)

---
kind: rule
id: P-0027
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: a change to the EA model (.qea) is planned
do: start from the latest .qea on any open branch and let only one branch change it at a time
because: the .qea is binary and cannot be merged
source: "2026-11-27: 'if we will touch the EA model, we better pull the latest version because it is a binary'"
added: 2026-11-27
approved: 2026-11-27
last_confirmed: 2026-11-27
private: false
---

