# Domain mutants not killed by tests/unit/domain (audit 2026-11-16, mutmut 3.8.1)

Kinds: message = changes only an error-message string (expected survivor); none-arg = passes None for an argument; logic = changes behaviour.

| Status | Mutant | Kind | Diff (first 160 chars) |
|---|---|---|---|
| survived | `iris.x_root_of_graph__mutmut_11` | none-arg | `-        raise InvalidIri(f"not the graph of an aggregate: {graph!r}") +        raise InvalidIri(None)` |
| survived | `iris.x_aggregate_iri__mutmut_2` | none-arg | `-    return DEFAULT_IRIS.aggregate(tenant, cls_type="", rp_path=rp_path, object_id=aggregate_id) +    return DEFAULT_IRIS.aggregate(tenant, cls_type=None, rp_pa` |
| survived | `iris.x_aggregate_iri__mutmut_9` | message | `-    return DEFAULT_IRIS.aggregate(tenant, cls_type="", rp_path=rp_path, object_id=aggregate_id) +    return DEFAULT_IRIS.aggregate(tenant, cls_type="XXXX", rp_` |
| survived | `iris.x_mint_aggregate_iri__mutmut_2` | none-arg | `-    return DEFAULT_IRIS.mint_aggregate(tenant_iri, cls_type="", rp_path=rp_path) +    return DEFAULT_IRIS.mint_aggregate(tenant_iri, cls_type=None, rp_path=rp_` |
| survived | `iris.x_mint_aggregate_iri__mutmut_7` | message | `-    return DEFAULT_IRIS.mint_aggregate(tenant_iri, cls_type="", rp_path=rp_path) +    return DEFAULT_IRIS.mint_aggregate(tenant_iri, cls_type="XXXX", rp_path=r` |
| survived | `iris.x_mint_part_iri__mutmut_1` | none-arg | `-    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type="") +    return DEFAULT_IRIS.mint_part(tenant=None, root=root_iri, cls_type="")` |
| survived | `iris.x_mint_part_iri__mutmut_3` | none-arg | `-    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type="") +    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type=None)` |
| survived | `iris.x_mint_part_iri__mutmut_7` | message | `-    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type="") +    return DEFAULT_IRIS.mint_part(tenant="XXXX", root=root_iri, cls_type="")` |
| survived | `iris.x_mint_part_iri__mutmut_8` | message | `-    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type="") +    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type="XXXX")` |
| survived | `iris.x_loaded_graph_iri__mutmut_1` | none-arg | `-    return DEFAULT_IRIS.mint_loaded_graph(tenant="", root=aggregate_iri) +    return DEFAULT_IRIS.mint_loaded_graph(tenant=None, root=aggregate_iri)` |
| survived | `iris.x_loaded_graph_iri__mutmut_5` | message | `-    return DEFAULT_IRIS.mint_loaded_graph(tenant="", root=aggregate_iri) +    return DEFAULT_IRIS.mint_loaded_graph(tenant="XXXX", root=aggregate_iri)` |
| survived | `iris.x_tenant_resource_name__mutmut_5` | logic | `-    last = tenant_iri.rsplit("/", 1)[-1] +    last = tenant_iri.rsplit("/", )[-1]` |
| survived | `iris.x_tenant_resource_name__mutmut_8` | logic | `-    last = tenant_iri.rsplit("/", 1)[-1] +    last = tenant_iri.rsplit("/", 2)[-1]` |
| survived | `iris.x_tenant_resource_name__mutmut_9` | logic | `-    last = tenant_iri.rsplit("/", 1)[-1] +    last = tenant_iri.rsplit("/", 1)[+1]` |
| survived | `iris.x_effective_policy__mutmut_9` | message | `-        "deployment": settings.deployment or "", +        "deployment": settings.deployment or "XXXX",` |
| survived | `iris.x__differences__mutmut_2` | logic | `-        if isinstance(stored[name], dict) and isinstance(configured[name], dict): +        if isinstance(stored[name], dict) or isinstance(configured[name], di` |
| survived | `iris.x_draw_id__mutmut_10` | logic | `-    return "".join(secrets.choice(alphabet) for _ in range(spec.length or 0)) +    return "".join(secrets.choice(alphabet) for _ in range(spec.length or 1))` |
| survived | `iris.x__alternation__mutmut_2` | logic | `-    return "(?:" + "/".join(map(re.escape, sorted(types))) + ")" if types else _NOTHING +    return "(?:" + "/".join(map(re.escape, sorted(types))) + ")" if (t` |
| survived | `iris.x__compile__mutmut_20` | none-arg | `-            parts.append(f"(?P={name})") +            parts.append(None)` |
| survived | `iris.x__compile__mutmut_21` | none-arg | `-            seen.add(name) +            seen.add(None)` |
| survived | `iris.x__compile__mutmut_26` | logic | `-    return re.compile("".join(parts), re.DOTALL) +    return re.compile("".join(parts), )` |
| survived | `iris.xǁIrisǁ__init____mutmut_2` | none-arg | `-    own = settings.model_copy(deep=True) +    own = settings.model_copy(deep=None)` |
| survived | `iris.xǁIrisǁ__init____mutmut_3` | logic | `-    own = settings.model_copy(deep=True) +    own = settings.model_copy(deep=False)` |
| no tests | `iris.xǁIrisǁpart_needs_type__mutmut_1` | logic | `-    return _TYPE_PLACEHOLDER in self._template("part_template") +    return _TYPE_PLACEHOLDER not in self._template("part_template")` |
| no tests | `iris.xǁIrisǁpart_needs_type__mutmut_2` | none-arg | `-    return _TYPE_PLACEHOLDER in self._template("part_template") +    return _TYPE_PLACEHOLDER in self._template(None)` |
| no tests | `iris.xǁIrisǁpart_needs_type__mutmut_3` | message | `-    return _TYPE_PLACEHOLDER in self._template("part_template") +    return _TYPE_PLACEHOLDER in self._template("XXpart_templateXX")` |
| no tests | `iris.xǁIrisǁpart_needs_type__mutmut_4` | message | `-    return _TYPE_PLACEHOLDER in self._template("part_template") +    return _TYPE_PLACEHOLDER in self._template("PART_TEMPLATE")` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs__mutmut_1` | none-arg | `-    tenant = self._probe_tenant() +    tenant = None` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs__mutmut_2` | none-arg | `-    if tenant is not None:  # else no id can be drawn: minting a tenant fails on its own, loudly +    if tenant is None:  # else no id can be drawn: minting a ` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_3` | message | `-    taken = {str(tenant): "tenant"} +    taken = {str(tenant): "XXtenantXX"}` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_4` | message | `-    taken = {str(tenant): "tenant"} +    taken = {str(tenant): "TENANT"}` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_5` | message | `-        ("access", self.access), +        ("XXaccessXX", self.access),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_6` | message | `-        ("access", self.access), +        ("ACCESS", self.access),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_7` | message | `-        ("meta", self.meta), +        ("XXmetaXX", self.meta),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_8` | message | `-        ("meta", self.meta), +        ("META", self.meta),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_9` | message | `-        ("registry", self.registry), +        ("XXregistryXX", self.registry),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_10` | message | `-        ("registry", self.registry), +        ("REGISTRY", self.registry),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_11` | message | `-        ("provenance", self.provenance), +        ("XXprovenanceXX", self.provenance),` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_18` | none-arg | `-        taken[iri] = name +        taken[iri] = None` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_19` | none-arg | `-            found = pattern.fullmatch(iri) +            found = None` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_24` | none-arg | `-            if found is not None and self._belongs(found, str(tenant)): +            if found is not None and self._belongs(found, None):` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_27` | none-arg | `-            if found is not None and self._belongs(found, str(tenant)): +            if found is not None and self._belongs(found, str(None)):` |
| survived | `iris.xǁIrisǁ_require_distinct_graphs_of__mutmut_28` | none-arg | `-                    f"the {name} template mints an IRI that reads as an aggregate: {iri!r}" +                    None` |
| survived | `iris.xǁIrisǁ_require_application_apart__mutmut_2` | message | `-    refusal = "the application's IRIs read as a tenant's under these templates" +    refusal = "XXthe application's IRIs read as a tenant's under these templat` |
| survived | `iris.xǁIrisǁ_require_application_apart__mutmut_3` | logic | `-    refusal = "the application's IRIs read as a tenant's under these templates" +    refusal = "the application's iris read as a tenant's under these templates` |
| survived | `iris.xǁIrisǁ_require_application_apart__mutmut_16` | none-arg | `-        self.is_aggregate(application, tenant) or self.is_loaded_graph(application, tenant) +        self.is_aggregate(application, tenant) or self.is_loaded_g` |
| survived | `iris.xǁIrisǁ_require_application_apart__mutmut_17` | none-arg | `-        self.is_aggregate(application, tenant) or self.is_loaded_graph(application, tenant) +        self.is_aggregate(application, tenant) or self.is_loaded_g` |
| survived | `iris.xǁIrisǁ_require_application_apart__mutmut_21` | none-arg | `-        raise InvalidIri(f"{refusal}: the tenant {str(tenant)!r} is one of its aggregates") +        raise InvalidIri(f"{refusal}: the tenant {str(None)!r} is ` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_4` | none-arg | `-        str(self._aggregate(application, kind, "probe", draw_id(spec))) +        str(None)` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_8` | none-arg | `-        str(self._aggregate(application, kind, "probe", draw_id(spec))) +        str(self._aggregate(application, kind, "probe", None))` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_22` | none-arg | `-    root = aggregates[0] if aggregates else application +    root = None` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_23` | logic | `-    root = aggregates[0] if aggregates else application +    root = aggregates[0] if (aggregates) and False else application` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_29` | none-arg | `-            root=root, +            root=None,` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_30` | none-arg | `-            type=kind, +            type=None,` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_47` | none-arg | `-    loaded = self._fill( -        self._template("loaded_graph_template"), -        tenant=application, -        root=root, -        type=LOADED_GRAPH_TYPE, - ` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_50` | none-arg | `-        root=root, +        root=None,` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_51` | none-arg | `-        type=LOADED_GRAPH_TYPE, +        type=None,` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_52` | none-arg | `-        id=draw_id(spec), +        id=None,` |
| survived | `iris.xǁIrisǁ_application_probes__mutmut_66` | none-arg | `-    return [*aggregates, *map(str, parts), str(loaded)] +    return [*aggregates, *map(str, parts), str(None)]` |
| survived | `iris.xǁIrisǁ_probe_types__mutmut_2` | logic | `-    return types if _TYPE_PLACEHOLDER in self._template(slot) else frozenset({""}) +    return types if (_TYPE_PLACEHOLDER in self._template(slot)) or True els` |
| survived | `iris.xǁIrisǁ_probe_types__mutmut_6` | message | `-    return types if _TYPE_PLACEHOLDER in self._template(slot) else frozenset({""}) +    return types if _TYPE_PLACEHOLDER in self._template(slot) else frozense` |
| survived | `iris.xǁIrisǁ_new_id__mutmut_5` | none-arg | `-    raise InvalidIri(f"no id that is not a reserved word after {_MAX_RESERVED_REDRAWS} draws") +    raise InvalidIri(None)` |
| survived | `iris.xǁIrisǁtenant__mutmut_5` | none-arg | `-        raise NotFound(f"no tenant {tenant_id!r}") +        raise NotFound(None)` |
| survived | `iris.xǁIrisǁaggregate__mutmut_5` | none-arg | `-        raise NotFound(f"no aggregate {object_id!r}") +        raise NotFound(None)` |
| survived | `iris.xǁIrisǁprincipal__mutmut_4` | logic | `-            **self._fixed, issuer=issuer.rstrip("/"), sub=quote(sub, safe="") +            issuer=issuer.rstrip("/"), sub=quote(sub, safe="")` |
| survived | `iris.xǁIrisǁprincipal__mutmut_12` | message | `-            **self._fixed, issuer=issuer.rstrip("/"), sub=quote(sub, safe="") +            **self._fixed, issuer=issuer.rstrip("XX/XX"), sub=quote(sub, safe=""` |
| survived | `iris.xǁIrisǁprincipal__mutmut_17` | message | `-            **self._fixed, issuer=issuer.rstrip("/"), sub=quote(sub, safe="") +            **self._fixed, issuer=issuer.rstrip("/"), sub=quote(sub, safe="XXXX"` |
| survived | `iris.xǁIrisǁ_reads_reserved__mutmut_1` | none-arg | `-    tenant_id = groups.get("tenant_id") +    tenant_id = None` |
| survived | `iris.xǁIrisǁ_reads_reserved__mutmut_2` | none-arg | `-    tenant_id = groups.get("tenant_id") +    tenant_id = groups.get(None)` |
| survived | `iris.xǁIrisǁ_reads_reserved__mutmut_3` | message | `-    tenant_id = groups.get("tenant_id") +    tenant_id = groups.get("XXtenant_idXX")` |
| survived | `iris.xǁIrisǁ_reads_reserved__mutmut_4` | message | `-    tenant_id = groups.get("tenant_id") +    tenant_id = groups.get("TENANT_ID")` |
| survived | `iris.xǁIrisǁtenant_of_access__mutmut_13` | none-arg | `-        raise InvalidIri(f"not an access record IRI: {access_record_iri!r}") from error +        raise InvalidIri(None) from error` |
| no tests | `exceptions.xǁKeyConflictǁ__init____mutmut_1` | none-arg | `-    super().__init__(*args, iris=iris) +    super().__init__(*args, iris=None)` |
| no tests | `exceptions.xǁKeyConflictǁ__init____mutmut_2` | logic | `-    super().__init__(*args, iris=iris) +    super().__init__(iris=iris)` |
| no tests | `exceptions.xǁKeyConflictǁ__init____mutmut_3` | logic | `-    super().__init__(*args, iris=iris) +    super().__init__(*args, )` |
| no tests | `exceptions.xǁKeyConflictǁ__init____mutmut_4` | none-arg | `-    self.keys = tuple(keys) +    self.keys = None` |
| no tests | `exceptions.xǁKeyConflictǁ__init____mutmut_5` | none-arg | `-    self.keys = tuple(keys) +    self.keys = tuple(None)` |
| no tests | `exceptions.xǁMigrationFailedǁ__init____mutmut_1` | message | `-    self, *args: object, schema: str = "", migration: str = "", cause: str = "" +    self, *args: object, schema: str = "XXXX", migration: str = "", cause: str` |
| no tests | `exceptions.xǁMigrationFailedǁ__init____mutmut_2` | message | `-    self, *args: object, schema: str = "", migration: str = "", cause: str = "" +    self, *args: object, schema: str = "", migration: str = "XXXX", cause: str` |
| no tests | `exceptions.xǁMigrationFailedǁ__init____mutmut_3` | message | `-    self, *args: object, schema: str = "", migration: str = "", cause: str = "" +    self, *args: object, schema: str = "", migration: str = "", cause: str = "` |
| no tests | `exceptions.xǁMigrationFailedǁ__init____mutmut_4` | none-arg | `-    self.schema = schema +    self.schema = None` |
| no tests | `exceptions.xǁMigrationFailedǁ__init____mutmut_5` | none-arg | `-    self.migration = migration +    self.migration = None` |
| no tests | `exceptions.xǁMigrationFailedǁ__init____mutmut_6` | none-arg | `-    self.cause = cause +    self.cause = None` |
| no tests | `exceptions.xǁMessageLimitExceededǁ__init____mutmut_1` | none-arg | `-    super().__init__(f"message limit {limit} reached") +    super().__init__(None)` |
| no tests | `exceptions.xǁMessageLimitExceededǁ__init____mutmut_2` | none-arg | `-    self.limit = limit +    self.limit = None` |
| survived | `tenant_move.x_check_graphs__mutmut_11` | message | `-            raise InvalidBody("the dump has a quad in the default graph") +            raise InvalidBody("XXthe dump has a quad in the default graphXX")` |
| survived | `tenant_move.x_check_graphs__mutmut_22` | none-arg | `-            or iris.is_loaded_graph(tenant, graph) +            or iris.is_loaded_graph(None, graph)` |
| survived | `sparql.x__string__mutmut_13` | none-arg | `-    escaped = _AFTER_BACKSLASH.sub(lambda m: f"\\U{ord(m.group()):08X}", escaped) +    escaped = _AFTER_BACKSLASH.sub(lambda m: None, escaped)` |
| survived | `sparql.x__string__mutmut_14` | none-arg | `-    escaped = _AFTER_BACKSLASH.sub(lambda m: f"\\U{ord(m.group()):08X}", escaped) +    escaped = _AFTER_BACKSLASH.sub(lambda m: f"\\U{ord(None):08X}", escaped)` |
| survived | `sparql.x__literal__mutmut_6` | none-arg | `-            raise SparqlError(f"not a valid language tag: {value.language!r}") +            raise SparqlError(None)` |
| survived | `sparql.x_term__mutmut_10` | none-arg | `-            raise SparqlError(f"not a valid blank node label: {str(value)!r}") +            raise SparqlError(f"not a valid blank node label: {str(None)!r}")` |
| survived | `sparql.x_term__mutmut_13` | none-arg | `-        f"term() takes an rdflib URIRef, Literal or BNode, not {type(value).__name__}" +        f"term() takes an rdflib URIRef, Literal or BNode, not {type(No` |
| survived | `sparql.x__joined__mutmut_3` | none-arg | `-    if raw := [type(p).__name__ for p in items if not isinstance(p, SparqlTerm)]: +    if raw := [type(None).__name__ for p in items if not isinstance(p, Sparq` |
| survived | `sparql.x_join__mutmut_3` | message | `-    return _joined(" ", parts, "join") +    return _joined(" ", parts, None)` |
| survived | `sparql.x_join__mutmut_8` | message | `-    return _joined(" ", parts, "join") +    return _joined(" ", parts, "XXjoinXX")` |
| survived | `sparql.x_join__mutmut_9` | message | `-    return _joined(" ", parts, "join") +    return _joined(" ", parts, "JOIN")` |
| survived | `sparql.x_union__mutmut_3` | message | `-    return _joined(" UNION ", parts, "union") +    return _joined(" UNION ", parts, None)` |
| survived | `sparql.x_union__mutmut_9` | message | `-    return _joined(" UNION ", parts, "union") +    return _joined(" UNION ", parts, "XXunionXX")` |
| survived | `sparql.x_union__mutmut_10` | message | `-    return _joined(" UNION ", parts, "union") +    return _joined(" UNION ", parts, "UNION")` |
| survived | `sparql.x_match_patterns__mutmut_3` | none-arg | `-        raise SparqlError(f"not a plain variable name: {variable!r}") +        raise SparqlError(None)` |
| survived | `sparql.x_value_patterns__mutmut_3` | none-arg | `-        raise SparqlError(f"not a plain variable name: {subject!r}") +        raise SparqlError(None)` |
| survived | `sparql.x_count__mutmut_6` | none-arg | `-        raise SparqlError(f"a count is a non-negative integer, not {value!r}") +        raise SparqlError(None)` |
| survived | `sparql.x_order_by__mutmut_3` | none-arg | `-            raise SparqlError(f"not a plain variable name: {variable!r}") +            raise SparqlError(None)` |
| survived | `sparql.x_checked_group__mutmut_3` | message | `-        raise SparqlError("has a codepoint escape (\\u or \\U); write the character itself") +        raise SparqlError("XXhas a codepoint escape (\\u or \\U);` |
| survived | `sparql.x_checked_group__mutmut_7` | none-arg | `-    tree = _parsed(text, template) +    tree = _parsed(text, None)` |
| survived | `sparql.x_checked_group__mutmut_25` | none-arg | `-        raise SparqlError(_TOO_LONG) from error +        raise SparqlError(None) from error` |
| survived | `sparql.x__parsed__mutmut_5` | message | `-        raise SparqlError("does not parse alone as a group graph pattern") from error +        raise SparqlError("XXdoes not parse alone as a group graph patte` |
| survived | `sparql.x__any_node_problem__mutmut_2` | message | `-            return "contains GRAPH or SERVICE: a step works inside one graph" +            return "XXcontains GRAPH or SERVICE: a step works inside one graphXX` |
| survived | `sparql.x__any_node_problem__mutmut_6` | message | `-            return "has a prefixed name; write the full IRI in angle brackets" +            return "XXhas a prefixed name; write the full IRI in angle brackets` |
| survived | `sparql.x__any_node_problem__mutmut_7` | logic | `-            return "has a prefixed name; write the full IRI in angle brackets" +            return "has a prefixed name; write the full iri in angle brackets"` |
| survived | `sparql.x__template_node_problem__mutmut_3` | message | `-        return "has a blank node (_:, [ ] or a collection), which a migration cannot mint" +        return "XXhas a blank node (_:, [ ] or a collection), which` |
