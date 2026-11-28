<!-- Secondary input, never groomed: GitHub issue #435 (meaningfy-ws/rdf-persistence), fetched 2026-11-28, state OPEN. Folded into this change (DEC-1). The EPIC (../proposal.md) supersedes it. -->

# #435 uml2linkml: accept a Realisation from an Object to its classifier

## Summary

`rp-uml2linkml` refuses a Realisation connector from an Object to the class it instantiates. Any connector type other than Association, Dependency and Generalization (and a workflow's state flows) is a `no_rule` problem (`rdf_persistence_generation/uml/qea.py` `LINK_KINDS`, l.126-128 and l.545-547), so generation stops.

## Context

Consumer: MWB2 (rdf-persistence v0.15.0), EA round 27. The modeller drew a Realisation from each role-definition Object (`admin`, `owner`, `member`, `reviewer`, `semantic_expert`, `business_expert`) to the drawn toolkit class `rp:RoleDefinition`, to show on the diagram which class each instance realises. `make generate` then failed with six findings:

```
[no_rule] admin -> rp:RoleDefinition: Realisation connector: no rule converts it
```

The links were removed to unblock the round; the modeller wants them back.

## Expected behaviour / proposed capability

- A Realisation from an Object to a class is accepted as the visible form of the Object's classifier: it converts to nothing beyond what the classifier already gives (`roles.py` reads the classifier).
- If the Realisation and the Object's classifier name different classes, the converter reports it (the two statements disagree), rather than picking one.
- An Object drawn with a Realisation but no classifier may take the Realisation's target as its classifier, or be reported; the toolkit decides.

## Why it belongs in rdf-persistence

The converter owns which UML constructs a model may use. Realising an instance's class is standard UML notation on object diagrams; a consumer cannot accept it on its side without editing the converter.

## Impact on the consumer

Must have (2026-11-28): MWB2 requires these links on its object diagrams; it draws the role objects without them only until this lands.

