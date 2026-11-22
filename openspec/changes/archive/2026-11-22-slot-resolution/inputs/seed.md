# Seed: slot resolution (#277, #278)

Recorded after delivery, on the owner's request (2026-11-22): the work ran as a bug fix outside an
EPIC, with its decisions logged in PR #289. This file keeps what started it.

## The brief (owner, 2026-11-22)

Bug-fix flow, tests first from each issue's toy reproduction, the failing shape added to the toy so
the toolkit's own suite covers it. The issues block MWB2's `v2-02` phase B (mapping-workbench-v2
PR #101). Both come from how a slot or property is resolved to the toolkit's own slots:

- **#277:** a business identifier (slot `identifier`, `slot_uri: dcterms:identifier`, string) is
  refused as "not an IRI" because the toolkit's `id` uses the same property. The identifier slot
  (`identifier: true`) is the object's IRI and never a triple, so it must never take part in
  resolving a property.
- **#278:** a module's own slot named `version` resolves to the toolkit's internal version. In the
  toy the value is silently dropped; in MWB2 every package write is refused. Resolve slots by their
  owner and IRI, not by bare name. If an application name truly collides with an internal one, the
  generator refuses it with a hard check naming both; it never drops data silently.

Scope: schema and vocabulary resolution and the mapper, plus a generator check if needed.

## #277 as filed

A consumer slot on `dcterms:identifier` with range `string` cannot hold a value:
`422 invalid-body: identifier: Value is not of Node Kind sh:IRI`. The class's shape has two property
shapes on `dcterms:identifier`: the consumer's (`sh:Literal`, `xsd:string`) and the toolkit `id`'s
(`sh:nodeKind sh:IRI`). `rp-generate` reports no problem; a later schema change makes the lock check
report "range changed from xsd:anyURI to xsd:string: dcterms:identifier of Book". Expected: the
identifier slot contributes no property shape on `dcterms:identifier` (the converter's DEC-4: a
`dct:identifier` attribute is a business identifier, not the toolkit's `id`), or `rp-generate`
refuses the schema naming both slots.

## #278 as filed

A consumer module that defines its own slot `version` (`dcat:version`, string) gets the toolkit's
bookkeeping slot (`rp_core.yaml`, `rp:version`) instead. In the toy, `POST` with `"version": "2nd"`
answers 201 and the value is silently dropped. In a larger consumer schema the SHACL shape has the
property on `rp:version` while the JSON-LD context maps `version` to `dcat:version`, so every write
is refused (`Node <…> is closed. It cannot have value`). When the slot is defined in the root schema
itself, it wins. Expected: the consumer's slot is kept (the toolkit's bookkeeping slots take no part
in name resolution of domain classes) or `rp-generate` refuses with a hard check naming both
definitions; never a silent drop or a context and shape that disagree.
