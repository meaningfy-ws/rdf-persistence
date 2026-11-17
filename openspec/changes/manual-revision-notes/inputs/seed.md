<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: manual revision notes (developer, 2026-11-16)

## Seed text

The developer's notes from a manual revision of the code, verbatim:

> - does it matetr which cripto graphy we use? can we use one of the quantum resustent algorithms? HS512 ML-DSA-65
> FN-DSA-512    , or similar ones,
> - why is jwks implementig so low level stuff, we coudl keep it , i just fear we migth be reinvinting teh weheel so feel free to adopt a amtur library
> - idem, feel free to adopt a mature library for _http.py, why do we have it?
> - but again perhas we need those abobve, so just keep them i just doubt
> - warning, all teh constants, I repeat all the constants must be move somweher close to teh root and adopt a contant/parameter management system exatcly how ti is done in the ted-sws pipeline, or hwo it is done in the mapping-suite-sdk (MSSDK) both siblings repos
> - but maybe NOT all teh constants, I see for exampel in teh zytadel adapter, the constats there are path slugs, ... maybe thay must remain like this, and only what could be a variable must move to that __init__.py that defined variabels
> - the logging must be aligned to best loggin practices in OpenTelmetry
> - do we need that fusekiStore adapter? is it so ... necessary? whay is it an http adpater and not an rdflib adapter? or a similar library to rdflib (if anythign faster exists e.g. from oxygraoh i am not sure it is generic or can be like in rdflib, but still rdflib adapter would appeal to me as mosr reliable/elegant than http-based adaptr)
> - media types could be more pehaps,a nd could be an enum in linkml (and otehr keywords, arent they already keywords somejwre in an htto library ?)
> - for IRIs, rdflib again has tools for managing and manipulatin URIs, can you use anything there ? but again we will need some policy templates somehwre ...
> - for SPARQL did we need to implement ig from scratch or osuld we have re-used what is in Sparql Wrapper? and did we need SparqlTerm class (surely it is implemenetd elsewhere already)? but maybe we need it ...
> - the negotiation.py has again a bunch of keywords are they defined anywhere in the http libraries? are there any libraries fro content negitioton, already implementing it? justr euse anythign mature dont reinvent the wheel?
> - on openApi entrypint, is there anythign that can ... lift an openapi schema spceification itn executable blocks? how about libraries like https://github.com/spec-first/connexion which is a spec first library (can you build on top?) are there oterh ones that are better? oterhwise sure we biuld our own, if there arte limitation we cannto overcome, like user control authintication etc ... but we must not reinvent the wheel reuse; and it seems to support pluggability, study it abit
> - I spotted an anti pattern (must not happen anywhere in the code) of build a distionnary with hardcoded dict keys line 126 in unique_keys.py service , never use bare dict key, dicts shall rerely be used, and instead prefer models, to encapsulate concepts.
> - inside the mode solder I am surprise to see models that are uder /adapters and under /servies, the models are models, they are domain or technical objects, they must be broiken down into coherent groups that are treated as submodules, so then we could have 2 level organisation, whic in fact is the correct way to structe laterger apps. take inspiration from ted sws and mssdk proejcts, there the thematic modules are lvl1 distinctions, and then each thematric moduel then has its own adapters/models/services/entrypoints , but some modules then are more on teh domain, and adapters, so they end up being reused by otehrs, and some otehr thematic moduels end up mor eon the consumtipon side so tehy end up having more services ro entrypoitns. this way we avoinf having a very long list of services, or a very long list of domain models, etc ... ; so in linkml fodler we shall have likely a flat list of fiels or  groupped by thematic modules, that wil be missored then itn teh generated code.
>
> - then indeed we wanty to also generate the code from linkml within this repo, for teh models we use within the repo, and also have good reliable generators for that, which could be used also outside teh repo for the apps building on topf of this toolkit; so for this reason I believe that the generators (all of them) must be a sibling repo to teh rdf_persistence (not within), and the tests we have thests forthe generatos shall be separate (e2e, feature, unit, integration, etc..., and thests for teh library itself, the rdf_persistence, the whoel spectrum)
>
> what do you think ?
> note that in a previous epic we have also don a tsate of teh art review and we identified libraries soe of them more mature, that we could reuse (or indeed reimplement by getting inspired from them)
>
> please make an extensive analisys based on what I just told you and write down all teh findings.
> finally in a separate inptu file you will provide all the improvements you think we shall make based on my comments and you findings, and reasons why, and in anoterh file you will tell me all teh things we shall keep as are and reasons why. finally we want to make good implementations for thinsg do not exist, but we want to maximise reuse for things that exist (and are mature and used).
>
> fianlly ciommit and cerate a pr

## Where the analysis lives

- `analysis.md`: the findings, per note.
- `improvements.md`: what to change, and why.
- `keep.md`: what to keep as it is, and why.
