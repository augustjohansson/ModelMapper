import json
import requests
from jsonschema import validate, ValidationError
import re
import os
from urllib.parse import urlparse
from pathlib import Path
from ontologyparser import OntologyParser
from parametermapper import ParameterMapper
from jsonld_exporter import export_jsonld


class JSONLoader:
    @staticmethod
    def load(source):
        # Accept Path or str
        source = Path(source)

        # If it looks like a URL → load from web
        if urlparse(str(source)).scheme in ("http", "https"):
            response = requests.get(str(source))
            response.raise_for_status()
            return response.json()

        # Else → treat as local file
        if not source.is_file():
            raise ValueError(f"File does not exist: {source}")

        return json.loads(source.read_text(encoding="utf-8"))


class JSONValidator:
    @staticmethod
    def validate(data, schema_url):
        schema = JSONLoader.load(schema_url)
        try:
            validate(instance=data, schema=schema)
            print("JSON is valid.")
        except ValidationError as e:
            print(f"JSON validation error: {e.message}")
            raise


class JSONWriter:
    @staticmethod
    def write(data, output_path):
        with open(output_path, "w") as file:
            json.dump(data, file, indent=4)


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
    # ontology_ref = "https://w3id.org/emmo/domain/battery-model-lithium-ion/latest"
    ontology_ref = "assets/battery-model-lithium-ion.ttl"
    # input_json = "https://raw.githubusercontent.com/cidetec-energy-storage/cideMOD/main/data/data_Chen_2020/params_tuned_vOCPexpression.json"
    input_json = "/tmp/h0b-opt.json"
    output_json_path = "converted_battery_parameters.json"
    defaults_json_path = "defaults_used.json"
    template_url = "https://raw.githubusercontent.com/BIG-MAP/ModelMapper/main/assets/bpx_template.json"
    # input_type = "cidemod"
    input_type = "battmo.m"
    # output_type = 'bpx'
    # output_type = "battmo.m"
    output_type = "jsonld"

    # Initialize the OntologyParser
    ontology_parser = OntologyParser(ontology_ref)

    # Load the input JSON file
    input_data = JSONLoader.load(input_json)
    # print("Input Data:", json.dumps(input_data, indent=4))

    if output_type == "jsonld":

        export_jsonld(
            ontology_parser=ontology_parser,
            input_type=input_type,
            input_data=input_data,
            output_path="file.jsonld",
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
        template_data = JSONLoader.load(template_url)
        template_data.pop(
            "Validation", None
        )  # Remove validation if it exists in the template

        # Map the parameters using the mappings from the ontology
        parameter_mapper = ParameterMapper(
            mappings, template_data, input_json, output_type, input_type
        )
        output_data = parameter_mapper.map_parameters(input_data)
        defaults_used_data = list(parameter_mapper.defaults_used)
        print("Output Data:", json.dumps(output_data, indent=4))

    # # Write the output JSON file
    # JSONWriter.write(output_data, output_json_path)

    # # Write the defaults used JSON file
    # JSONWriter.write(defaults_used_data, defaults_json_path)

    # # Load the DFN model
    # model = pybamm.lithium_ion.DFN()

    # # Load the parameter values
    # parameter_values = pybamm.ParameterValues.create_from_bpx('converted_battery_parameters.json')

    # # Define the experiment: Charge from SOC=0.01, then discharge
    # experiment = pybamm.Experiment([
    #     ("Charge at C/5 until 4.2 V",
    #      "Hold at 4.2 V until 1 mA",
    #      "Rest for 1 hour",
    #      "Discharge at C/5 until 2.5 V")
    # ])

    # # Create the simulation with the experiment
    # sim = pybamm.Simulation(model, experiment=experiment, parameter_values=parameter_values)

    # # Define initial concentration in negative and positive electrodes
    # parameter_values["Initial concentration in negative electrode [mol.m-3]"] = 0.0279 * parameter_values["Maximum concentration in negative electrode [mol.m-3]"]
    # parameter_values["Initial concentration in positive electrode [mol.m-3]"] = 0.9084 * parameter_values["Maximum concentration in positive electrode [mol.m-3]"]

    # # Solve the simulation
    # sim.solve()

    # # Plot the results
    # sim.plot()
