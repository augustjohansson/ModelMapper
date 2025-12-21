import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from jsonschema import validate, ValidationError

import BatteryModelMapper as bmm


def fix_battmo_porosity(label, input_path, input_data):
    if (
        label == "PositiveElectrodeCoatingPorosity"
        or label == "NegativeElectrodeCoatingPorosity"
    ):
        # Get the volume fraction of active material in the positive electrode coating
        vf_path = list(input_path)
        vf_path[-1] = "volumeFraction"
        vf_value = ParameterMapper.get_value_from_path(input_data, vf_path)
        if vf_value is None:
            ValueError(
                f"Could not find volumeFraction for porosity calculcation for {label}"
            )
        else:
            porosity = 1.0 - vf_value
            return porosity


if __name__ == "__main__":

    # Load references
    # ontology_ref = "https://w3id.org/emmo/domain/battery-model-lithium-ion/latest"
    ontology_ref = "assets/battery-model-lithium-ion.ttl"
    # template_ref = "https://raw.githubusercontent.com/BIG-MAP/ModelMapper/main/assets/bpx_template.json"
    template_ref = "assets/bpx_template.json"
    defaults_json_path = "defaults_used.json"

    # Specify input
    # input_json = "https://raw.githubusercontent.com/cidetec-energy-storage/cideMOD/main/data/data_Chen_2020/params_tuned_vOCPexpression.json"
    input_json = "/tmp/h0b-opt.json"
    # input_json = "/tmp/mj1.json"
    # input_type = "cidemod"
    input_type = "battmo.m"

    # Specify output
    # output_json = "mj1_bpx.json"
    # output_type = "bpx"
    # output_type = "battmo.m"
    output_json = "/tmp/h0b-opt.jsonld"
    output_type = "jsonld"

    # Initialize the OntologyParser
    ontology_parser = bmm.OntologyParser(ontology_ref)

    # Load the input JSON file
    input_data = bmm.JSONLoader.load(input_json)
    # print("Input Data:", json.dumps(input_data, indent=4))

    # Preprocessing
    preprocessor = bmm.PreprocessInput(input_type, input_data)
    input_data = preprocessor.process()

    if output_type == "jsonld":

        bmm.export_jsonld(
            ontology_parser=ontology_parser,
            input_type=input_type,
            input_data=input_data,
            output_path=output_json,
            cell_id="BattMo",
            cell_type="PouchCell",
        )

    else:

        mappings = ontology_parser.get_mappings(input_type, output_type)
        print(
            "Mappings:",
            json.dumps({str(k): str(v) for k, v in mappings.items()}, indent=4),
        )

        # Load the template JSON file
        template_data = bmm.JSONLoader.load(template_ref)
        template_data.pop(
            "Validation", None
        )  # Remove validation if it exists in the template

        # Map the parameters using the mappings from the ontology
        parameter_mapper = bmm.ParameterMapper(
            mappings, template_data, input_json, output_type, input_type
        )
        output_data = parameter_mapper.map_parameters(input_data)
        # defaults_used_data = list(parameter_mapper.defaults_used)
        bmm.JSONWriter().write(output_data, output_json)
        breakpoint()
