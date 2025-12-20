import json
from typing import Any, Dict, List, Optional, Set
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


def _localname(u: URIRef) -> str:
    s = str(u)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _curie(g, term: URIRef) -> str:
    try:
        return g.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)


def _first_literal_str(g, subj: URIRef, pred: URIRef) -> Optional[str]:
    for o in g.objects(subj, pred):
        return str(o)
    return None


def _label(g, term: URIRef) -> str:
    return (
        _first_literal_str(g, term, SKOS.prefLabel)
        or _first_literal_str(g, term, RDFS.label)
        or _curie(g, term)
    )


def _find_any_predicate_by_localname(g, candidates: Set[str]) -> Optional[URIRef]:
    for p in set(g.predicates()):
        if _localname(p) in candidates:
            return p
    return None


def _get_value_from_path(data: Any, keys: List[Any]) -> Any:
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
    for sc in g.objects(cls, RDFS.subClassOf):
        if isinstance(sc, BNode) and (sc, RDF.type, OWL.Restriction) in g:
            yield sc
    for ec in g.objects(cls, OWL.equivalentClass):
        if isinstance(ec, BNode) and (ec, RDF.type, OWL.Restriction) in g:
            yield ec


def _find_missing_values(ontology_parser, input_data, input_type):
    mapped_paths = set()
    for s in ontology_parser.graph.subjects():
        for p, o in ontology_parser.graph.predicate_objects(s):
            if p == ontology_parser.key_map.get("battmo.m"):
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


def export_jsonld(
    ontology_parser,
    input_type: str,
    input_data: Dict[str, Any],
    output_path: str,
    cell_id: str = "BattMo",
    cell_type: str = "PouchCell",
):
    g = ontology_parser.graph
    input_key = ontology_parser.key_map.get(input_type)
    if not input_key:
        raise ValueError(f"Invalid input type: {input_type}")

    out = {
        "@context": "https://w3id.org/emmo/domain/battery/context",
        "@graph": {
            "@id": cell_id,
            "@type": cell_type,
            "hasProperty": [],
        },
    }
    has_property = out["@graph"]["hasProperty"]

    for subject in set(g.subjects(input_key, None)):
        raw_path_literal = None
        path = None
        for p, o in g.predicate_objects(subject):
            if p == input_key:
                raw_path_literal = str(o)
                path = ontology_parser.parse_key(raw_path_literal)
                break
        if not path:
            continue
        value = _get_value_from_path(input_data, path)
        if value is None:
            continue

        prop_obj = {
            "@type": _curie(g, subject),
            "rdfs:label": _label(g, subject),
        }

        if _is_number_like(value):
            prop_obj["hasNumericalPart"] = {
                "@type": "Real",
                "hasNumericalValue": float(value),
            }
        elif isinstance(value, str):
            prop_obj["hasStringPart"] = {
                "@type": "String",
                "hasStringValue": value,
            }
        elif isinstance(value, (list, dict)):
            if isinstance(value, dict) and "functionname" in value:
                func_name = str(value["functionname"])
                prop_obj["hasStringPart"] = {
                    "@type": "String",
                    "hasStringValue": func_name,
                }
            else:
                # fallback for structured objects
                prop_obj["hasStringPart"] = {
                    "@type": "String",
                    "hasStringValue": str(value),
                }
        else:
            prop_obj["hasStringPart"] = {
                "@type": "String",
                "hasStringValue": str(value),
            }
        has_property.append(prop_obj)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # Find values not mapped
    missing = find_missing_values(ontology_parser, input_data, input_type)

    print("Number of JSON leaf values:", len(input_paths))
    print("Number of mapped values:", len(mapped_paths))
    print("Missing values:", len(missing))
    for p in missing:
        print("MISSING:", p)
