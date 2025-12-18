from parametermapper import ParameterMapper
from rdflib.namespace import SKOS, RDFS, RDF, OWL
from rdflib import BNode
import json


def find_unit_class(graph, parameter_class, hasMeasurementUnit):
    """
    Return the EMMO unit class (URIRef) for a parameter class,
    based on owl:Restriction on hasMeasurementUnit.
    """
    for sc in graph.objects(parameter_class, RDFS.subClassOf):
        if isinstance(sc, BNode) and (sc, RDF.type, OWL.Restriction) in graph:
            if graph.value(sc, OWL.onProperty) == hasMeasurementUnit:
                return graph.value(sc, OWL.someValuesFrom) or graph.value(
                    sc, OWL.allValuesFrom
                )
    return None


def find_unit_symbol(graph, unit_class, hasSymbolValue):
    if unit_class is None:
        return None
    for sym in graph.objects(unit_class, hasSymbolValue):
        return str(sym)
    return None


def _get_emmo_supertype(g, cls):
    """
    Find the first direct rdfs:subClassOf that looks like an EMMO class.
    """
    for sup in g.objects(cls, RDFS.subClassOf):
        s = str(sup)
        if "emmo" in s.lower() and "EMMO_" in s:
            return sup
    return None


def _curie(g, term):
    """Return a CURIE if possible, otherwise the full IRI as a string."""
    try:
        return g.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)


def _get_rdfs_label(g, term):
    for lbl in g.objects(term, RDFS.label):
        return str(lbl)
    return None


def _find_by_prefLabel(g, label: str):
    for s in g.subjects(SKOS.prefLabel, None):
        for lbl in g.objects(s, SKOS.prefLabel):
            if str(lbl) == label:
                return s
    return None


def _get_prefLabel(g, term):
    for lbl in g.objects(term, SKOS.prefLabel):
        return str(lbl)
    return None


def _find_unit_for_class(g, cls, hasMeasurementUnit_uri):
    for sc in g.objects(cls, RDFS.subClassOf):
        if isinstance(sc, BNode) and (sc, RDF.type, OWL.Restriction) in g:
            if g.value(sc, OWL.onProperty) == hasMeasurementUnit_uri:
                return g.value(sc, OWL.someValuesFrom) or g.value(sc, OWL.allValuesFrom)
    return None


def _find_symbol_for_unit(g, unit_cls, hasSymbolValue_uri):
    if unit_cls is None:
        return None
    for sym in g.objects(unit_cls, hasSymbolValue_uri):
        return str(sym)
    return None


def export_jsonld(
    ontology_parser,
    input_type: str,
    input_data: dict,
    output_path: str,
    cell_id: str = "BattMo",
    cell_type: str = "PouchCell",
):
    """
    Export mapped parameters as structured JSON-LD using EMMO/Battery context.
    """
    g = ontology_parser.graph
    input_key = ontology_parser.key_map.get(input_type)
    if not input_key:
        raise ValueError(f"Invalid input type: {input_type}")

    # Resolve ontology properties by label
    hasMeasurementUnit = _find_by_prefLabel(g, "hasMeasurementUnit")
    hasNumericalPart = _find_by_prefLabel(g, "hasNumericalPart")
    hasNumericalValue = _find_by_prefLabel(g, "hasNumericalValue")
    hasSymbolValue = _find_by_prefLabel(g, "hasSymbolValue")

    out = {
        "@context": "https://w3id.org/emmo/domain/battery/context",
        "@graph": {"@id": cell_id, "@type": cell_type, "hasProperty": []},
    }

    for subject in g.subjects():
        # find battmo.m path
        path = None
        for p, o in g.predicate_objects(subject):
            if p == input_key:
                path = ontology_parser.parse_key(str(o))
                break
        if not path:
            continue

        value = ParameterMapper.get_value_from_path(input_data, path)
        if value is None:
            continue

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue

        # Resolve ontology predicates (once, outside the loop ideally)
        hasMeasurementUnit = _find_by_prefLabel(g, "hasMeasurementUnit")
        hasSymbolValue = _find_by_prefLabel(g, "hasSymbolValue")

        # --- find unit from ontology ---
        unit_class = find_unit_class(g, subject, hasMeasurementUnit)
        unit_symbol = find_unit_symbol(g, unit_class, hasSymbolValue)

        unit_label = _get_prefLabel(g, unit_class)
        unit_type = _curie(g, unit_class) if unit_class else None

        unit_cls = _find_unit_for_class(g, subject, hasMeasurementUnit)
        symbol = _find_symbol_for_unit(g, unit_cls, hasSymbolValue)
        unit_label = _get_prefLabel(g, unit_cls)

        # prop_label = _get_prefLabel(g, subject) or str(subject)

        # prop = {
        #     "@type": prop_label,
        #     "hasNumericalPart": {"@type": "Real", "hasNumericalValue": numeric},
        # }

        # Use the ontology class IRI/CURIE as the primary type
        param_type = _curie(g, subject)

        # Add an EMMO supertype as an additional @type (optional but matches your request)
        emmo_type_node = _get_emmo_supertype(g, subject)
        types = [param_type]
        if emmo_type_node is not None:
            types.append(_curie(g, emmo_type_node))

        # Labels: prefer SKOS prefLabel, fallback to rdfs:label, fallback to CURIE/IRI
        label = _get_prefLabel(g, subject) or _get_rdfs_label(g, subject) or param_type

        prop = {
            # "@type": types if len(types) > 1 else types[0],
            "@type": _curie(g, subject),
            # "@id": _curie(g, subject),
            # “rdfs label for the description”
            # If you want it literally as rdfs:label in the output:
            "rdfs:label": label,
            "hasNumericalPart": {"@type": "Real", "hasNumericalValue": numeric},
        }

        if unit_class is not None:
            prop["hasMeasurementUnit"] = {"@type": unit_type}
            if unit_symbol is not None:
                prop["hasMeasurementUnit"]["hasSymbolValue"] = unit_symbol

        # if unit_cls is not None:
        #     prop["hasMeasurementUnit"] = {
        #         "@type": f"emmo:{unit_label}" if unit_label else str(unit_cls)
        #     }
        #     if symbol is not None:
        #         prop["hasMeasurementUnit"]["hasSymbolValue"] = symbol

        out["@graph"]["hasProperty"].append(prop)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
