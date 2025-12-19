from pathlib import Path
from urllib.parse import urlparse

import ast
import json
import requests

from rdflib import Graph, URIRef, OWL
from rdflib.namespace import RDF


class OntologyParser:
    def __init__(self, ontology_ref):
        self.graph = Graph()
        ontology_ref = Path(ontology_ref)

        if urlparse(str(ontology_ref)).scheme in ("http", "https"):
            response = requests.get(ontology_ref)
            response.raise_for_status()
            response_text = response.text
        elif ontology_ref.is_file():
            with open(ontology_ref, "r", encoding="utf-8") as f:
                response_text = f.read().replace("\r\n", "\n")
        else:
            raise ValueError(f"File does not exist: {ontology_ref}")

        self.graph.parse(data=response_text, format="ttl")

        self.key_map = {
            "bpx": URIRef(
                "https://w3id.org/emmo/domain/battery-model-lithium-ion#bmli_0a5b99ee_995b_4899_a79b_925a4086da37"
            ),
            "cidemod": URIRef(
                "https://w3id.org/emmo/domain/battery-model-lithium-ion#bmli_1b718841_5d72_4071_bb71_fc4a754f5e30"
            ),
            "battmo.m": URIRef(
                "https://w3id.org/emmo/domain/battery-model-lithium-ion#bmli_e5e86474_8623_48ea_a1cf_502bdb10aa14"
            ),
        }

    def parse_key(self, key):
        try:
            return ast.literal_eval(key)
        except (ValueError, SyntaxError) as e:
            print(f"Error parsing key: {key} - {e}")
            return []

    def get_mappings(self, input_type, output_type):
        input_key = self.key_map.get(input_type)
        output_key = self.key_map.get(output_type)
        if not input_key or not output_key:
            raise ValueError(
                f"Invalid input or output type: {input_type}, {output_type}"
            )

        mappings = {}
        for subject in self.graph.subjects():
            input_value = None
            output_value = None
            for predicate, obj in self.graph.predicate_objects(subject):
                if predicate == input_key:
                    input_value = self.parse_key(str(obj))
                elif predicate == output_key:
                    output_value = self.parse_key(str(obj))
            if input_value and output_value:
                mappings[tuple(input_value)] = tuple(output_value)
                print(f"Mapping added: {tuple(input_value)} -> {tuple(output_value)}")
        return mappings
