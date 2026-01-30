import json
import argparse
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


def run(
    input_file,
    input_type,
    output_file,
    output_type,
    cell_id,
    cell_type,
    ontology_ref="assets/battery-model-lithium-ion.ttl",
    template_ref="assets/bpx_template.json",
):

    # Initialize the OntologyParser
    ontology_parser = bmm.OntologyParser(ontology_ref)

    # Load the input JSON file
    input_data = bmm.JSONLoader.load(input_file)
    # print("Input Data:", json.dumps(input_data, indent=4))

    # Preprocessing
    preprocessor = bmm.PreprocessInput(input_type, input_data)
    input_data = preprocessor.process()

    if output_type == "jsonld":

        bmm.export_jsonld(
            ontology_parser=ontology_parser,
            input_type=input_type,
            input_data=input_data,
            output_path=output_file,
            cell_id=cell_id,
            cell_type=cell_type,
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
            mappings, template_data, input_file, output_type, input_type
        )
        output_data = parameter_mapper.map_parameters(input_data)
        # defaults_used_data = list(parameter_mapper.defaults_used)
        bmm.JSONWriter().write(output_data, output_file)


def input_parser()

    parser = argparse.ArgumentParser(description="Battery Model Mapper CLI")

    types = ["bpx", "cidemod", "battmo.m", "jsonld"]
    input_types = list(set(types) - {"jsonld"})
    output_types = types

    parser.add_argument("-input-file", required=True, help="Input filename")
    parser.add_argument("-input-type", required=True, help=f"Input type string (must be one of {input_types})")
    parser.add_argument(
        "-output-file", required=False, default="output.jsonld", help="Output filename"
    )
    parser.add_argument(
        "-output-type", required=False, default="jsonld", help=f"Output type string (must be one of {output_types})"
    )
    parser.add_argument(
        "-cell-id", required=False, default="Cell ID", help="Cell ID (eg BattMo) for JSON-LD output"
    )
    parser.add_argument(
        "-cell-type", required=False, default="Pouch", help="Cell Type (eg Pouch) for JSON-LD output"
    )
    parser.add_argument(
        "-ontology-ref",
        default="assets/battery-model-lithium-ion.ttl",
        help="Ontology file path",
    )
    parser.add_argument(
        "-template-ref", default="assets/bpx_template.json", help="Template file path"
    )
    return parser, input_types, output_types


if __name__ == "__main__":

    # Parse input
    parser, input_types, output_types = input_parser()
    args = parser.parse_args()

    # Check the input and output types
    if args.input_type not in input_types:
        raise ValueError(f"Invalid input type: {args.input_type}")
    if args.output_type not in output_types:
        raise ValueError(f"Invalid output type: {args.output_type}")

    run(
        input_file=args.input_file,
        input_type=args.input_type,
        output_file=args.output_file,
        output_type=args.output_type,
        cell_id=args.cell_id,
        cell_type=args.cell_type,
        ontology_ref=args.ontology_ref,
        template_ref=args.template_ref,
    )
