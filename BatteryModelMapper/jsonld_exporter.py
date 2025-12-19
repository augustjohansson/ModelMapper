import json
from typing import Any, Dict, List, Optional, Set, Union
from collections import Counter
from rdflib import BNode, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS


def _is_number_like(v: Any) -> bool:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return False
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def print_unit_predicate_fillers(g, unit_pred, top=10):
    restrictions = list(g.subjects(RDF.type, OWL.Restriction))
    fillers = []
    for r in restrictions:
        if g.value(r, OWL.onProperty) == unit_pred:
            f = g.value(r, OWL.someValuesFrom) or g.value(r, OWL.allValuesFrom)
            if f:
                fillers.append(f)
    c = Counter(fillers)
    print("[units] top fillers for inferred unit_pred:")
    for f, n in c.most_common(top):
        print(" ", n, f)


def infer_unit_predicate(g):
    """
    Infer which owl:onProperty is used for measurement units by looking for
    restrictions where the filler (someValuesFrom/allValuesFrom) repeats a lot.
    Unit classes tend to be reused across many parameters (e.g., UnitOne, Metre, Second).
    """
    restrictions = list(g.subjects(RDF.type, OWL.Restriction))
    if not restrictions:
        return None

    # Count (onProperty -> how many times its filler repeats)
    onp_to_fillers = {}
    for r in restrictions:
        onp = g.value(r, OWL.onProperty)
        filler = g.value(r, OWL.someValuesFrom) or g.value(r, OWL.allValuesFrom)
        if onp is None or filler is None:
            continue
        onp_to_fillers.setdefault(onp, []).append(filler)

    # Score each onProperty by "repetition" of fillers:
    # units repeat a lot -> high concentration on a few fillers
    scores = {}
    for onp, fillers in onp_to_fillers.items():
        c = Counter(fillers)
        # sum of squares emphasizes repetition on the same few fillers
        scores[onp] = sum(n * n for n in c.values())

    if not scores:
        return None

    best = max(scores.items(), key=lambda kv: kv[1])[0]
    return best


def _localname(u: URIRef) -> str:
    s = str(u)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _curie(g, term: URIRef) -> str:
    """Return a CURIE if namespace bindings exist, otherwise full IRI string."""
    try:
        return g.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)


def _first_literal_str(g, subj: URIRef, pred: URIRef) -> Optional[str]:
    for o in g.objects(subj, pred):
        return str(o)
    return None


def _label(g, term: URIRef) -> str:
    """Prefer skos:prefLabel, then rdfs:label, else CURIE/IRI."""
    return (
        _first_literal_str(g, term, SKOS.prefLabel)
        or _first_literal_str(g, term, RDFS.label)
        or _curie(g, term)
    )


def _find_any_predicate_by_localname(g, candidates: Set[str]) -> Optional[URIRef]:
    """
    Find a predicate URI in the graph whose local name matches any candidate.
    This avoids relying on skos:prefLabel existing on properties.
    """
    for p in set(g.predicates()):
        if _localname(p) in candidates:
            return p
    return None


def _get_value_from_path(data: Any, keys: List[Any]) -> Any:
    """
    Safely traverse dict/list according to keys.
    Returns None if missing/invalid; never prints.
    """
    cur = data
    try:
        for k in keys:
            if isinstance(k, str):
                k = k.strip()
            if isinstance(cur, dict):
                cur = cur[k]
            elif isinstance(cur, list):
                cur = cur[int(k)]
            else:
                return None
        return cur
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def _iter_restrictions(g, cls: URIRef):
    """
    Yield blank-node restrictions linked via rdfs:subClassOf or owl:equivalentClass.
    """
    # rdfs:subClassOf _:bnode
    for sc in g.objects(cls, RDFS.subClassOf):
        if isinstance(sc, BNode) and (sc, RDF.type, OWL.Restriction) in g:
            yield sc

    # owl:equivalentClass _:bnode
    for ec in g.objects(cls, OWL.equivalentClass):
        if isinstance(ec, BNode) and (ec, RDF.type, OWL.Restriction) in g:
            yield ec


def _find_unit_class(
    g, parameter_class: URIRef, unit_pred: Optional[URIRef]
) -> Optional[URIRef]:
    """
    Look for OWL restriction on unit_pred:
      [ a owl:Restriction ;
        owl:onProperty unit_pred ;
        owl:someValuesFrom UNIT ]  or allValuesFrom UNIT
    """
    if unit_pred is None:
        return None

    for r in _iter_restrictions(g, parameter_class):
        onp = g.value(r, OWL.onProperty)
        if onp != unit_pred:
            continue
        unit = g.value(r, OWL.someValuesFrom) or g.value(r, OWL.allValuesFrom)
        if isinstance(unit, URIRef):
            return unit
    return None


def _find_unit_symbol(
    g, unit_class: URIRef, symbol_pred: Optional[URIRef]
) -> Optional[str]:
    """
    Try to read unit symbol from the unit class via symbol_pred.
    If ontology doesn't model it that way, this returns None.
    """
    if symbol_pred is None:
        return None
    for o in g.objects(unit_class, symbol_pred):
        return str(o)
    return None


def _check_mapped_data(ontology_parser, input_data: Dict[str, Any]):

    # Check what's in the original input vs what's exported
    mapped_paths = set()

    for s in ontology_parser.graph.subjects():
        for p, o in ontology_parser.graph.predicate_objects(s):
            if p == ontology_parser.key_map["battmo.m"]:
                mapped_paths.add(tuple(ontology_parser.parse_key(str(o))))

    def collect_json_paths(data, prefix=()):
        paths = set()
        if isinstance(data, dict):
            for k, v in data.items():
                paths |= collect_json_paths(v, prefix + (k,))
        elif isinstance(data, list):
            for i, v in enumerate(data):
                paths |= collect_json_paths(v, prefix + (i,))
        else:
            paths.add(prefix)
        return paths

    input_paths = collect_json_paths(input_data)

    missing = sorted(p for p in input_paths if p not in mapped_paths)

    print("Number of JSON leaf values:", len(input_paths))
    print("Number of mapped values:", len(mapped_paths))
    print("Missing values:", len(missing))

    for p in missing:
        print("MISSING:", p)


def export_jsonld(
    ontology_parser,
    input_type: str,
    input_data: Dict[str, Any],
    output_path: str,
    cell_id: str = "BattMo",
    cell_type: str = "PouchCell",
    debug_units: bool = False,
):
    """
    Export mapped parameters as structured JSON-LD:

    {
      "@context": "https://w3id.org/emmo/domain/battery/context",
      "@graph": {
        "@id": "BattMo",
        "@type": "PouchCell",
        "hasProperty": [ ... ]
      }
    }

    Each property:
      "@type": <parameter class CURIE/IRI>
      "rdfs:label": <label>
      "hasNumericalPart": { "@type": "Real", "hasNumericalValue": <float> }
      "hasMeasurementUnit": { "@type": <unit class CURIE/IRI>, "hasSymbolValue": <symbol?> }
    """

    g = ontology_parser.graph

    # mapping predicate in the ontology for the chosen input_type (e.g., battmo.m)
    input_key = ontology_parser.key_map.get(input_type)
    if not input_key:
        raise ValueError(f"Invalid input type: {input_type}")

    # Resolve unit-related predicates by local name (robust)
    unit_pred = _find_any_predicate_by_localname(
        g,
        {
            # common names seen in EMMO-derived ontologies
            "hasMeasurementUnit",
            "hasUnit",
            "hasReferenceUnit",
            "hasUnitOfMeasure",
        },
    )

    # unit_pred = infer_unit_predicate(g)
    # print("[units] inferred unit_pred:", unit_pred)

    # print_unit_predicate_fillers(g, unit_pred)

    symbol_pred = _find_any_predicate_by_localname(
        g, {"hasSymbolValue", "symbol", "hasUnitSymbol"}
    )

    if debug_units:
        print("[units] unit_pred  =", unit_pred)
        print("[units] symbol_pred=", symbol_pred)

    out: Dict[str, Any] = {
        "@context": "https://w3id.org/emmo/domain/battery/context",
        "@graph": {
            "@id": cell_id,
            "@type": cell_type,
            "hasProperty": [],
        },
    }

    has_property = out["@graph"]["hasProperty"]

    # Iterate subjects that have a mapping path for this input_type
    for subject in set(g.subjects(input_key, None)):
        # Find the mapping path literal for this subject
        raw_path_literal = None
        path = None
        for p, o in g.predicate_objects(subject):
            if p == input_key:
                raw_path_literal = str(o)
                path = ontology_parser.parse_key(raw_path_literal)
                break

        if not path:
            continue

        # Extract value from input JSON
        value = _get_value_from_path(input_data, path)
        if value is None:
            continue

        # # Only map numeric values into hasNumericalPart for now
        # try:
        #     numeric = float(value)
        # except (TypeError, ValueError):
        #     continue

        # prop_obj: Dict[str, Any] = {
        #     # preferred: one @type = the parameter class itself (CURIE if possible)
        #     "@type": _curie(g, subject),
        #     # rdfs:label as requested (human readable)
        #     "rdfs:label": _label(g, subject),
        #     "hasNumericalPart": {
        #         "@type": "Real",
        #         "hasNumericalValue": numeric,
        #     },
        # }

        prop_obj: Dict[str, Any] = {
            "@type": _curie(g, subject),
            "rdfs:label": _label(g, subject),
        }

        # --- value handling (numeric / string / structured) ---
        if _is_number_like(value):
            numeric = float(value)
            prop_obj["hasNumericalPart"] = {
                "@type": "Real",
                "hasNumericalValue": numeric,
            }

            # # (units optional; keep your existing unit logic here if you want)
            # unit_class = _find_unit_class(g, subject, unit_pred) if unit_pred else None
            # if unit_class is not None:
            #     unit_type = _curie(g, unit_class)
            #     unit_obj: Dict[str, Any] = {"@type": unit_type}

            #     sym = (
            #         _find_unit_symbol(g, unit_class, symbol_pred)
            #         if symbol_pred
            #         else None
            #     )
            #     if sym is None and (
            #         "UnitOne" in unit_type or _localname(unit_class) == "UnitOne"
            #     ):
            #         sym = "1"
            #     if sym is not None:
            #         unit_obj["hasSymbolValue"] = sym

            #     prop_obj["hasMeasurementUnit"] = unit_obj

        elif isinstance(value, str):
            prop_obj["hasStringPart"] = {
                "@type": "String",
                "hasStringValue": value,
            }
            print("[string] ", _curie(g, subject), "=", value)

        elif isinstance(value, (list, dict)):
            # e.g. lookup tables, structured objects
            if "functionname" in value:
                func_name = str(value["functionname"])
                prop_obj["hasStringPart"] = {
                    "@type": "String",
                    "hasStringValue": func_name,
                }
            else:
                breakpoint()
            print("[json] ", _curie(g, subject), "=", value)

        else:
            # fallback: keep it rather than dropping it
            prop_obj["hasStringPart"] = {
                "@type": "String",
                "hasStringValue": str(value),
            }
            print("[other] ", _curie(g, subject), "=", value)

        # Derive unit from ontology restrictions (if present)
        unit_class = _find_unit_class(g, subject, unit_pred) if unit_pred else None

        if unit_class is not None:
            unit_type = _curie(g, unit_class)
            unit_obj: Dict[str, Any] = {"@type": unit_type}

            sym = _find_unit_symbol(g, unit_class, symbol_pred) if symbol_pred else None

            # Safe fallback for UnitOne if symbol isn't modelled
            if sym is None and (
                "UnitOne" in unit_type or _localname(unit_class) == "UnitOne"
            ):
                sym = "1"

            if sym is not None:
                unit_obj["hasSymbolValue"] = sym

            prop_obj["hasMeasurementUnit"] = unit_obj

            if debug_units:
                print(
                    "[units] OK:", _curie(g, subject), "->", unit_type, "symbol:", sym
                )
        else:
            if debug_units:
                print("[units] NONE:", _curie(g, subject))

        has_property.append(prop_obj)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # Final check of mapped vs input data
    _check_mapped_data(ontology_parser, input_data)
