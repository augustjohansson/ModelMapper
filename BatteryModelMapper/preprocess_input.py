class PreprocessInput:
    def __init__(self, input_type, input_data):
        self.input_type = input_type
        self.input_data = input_data

    def process(self):
        if self.input_type == "cidemod":
            return self._process_cidemod()
        elif self.input_type == "battmo.m":
            return self._process_battmo_m()
        else:
            raise ValueError(f"Unsupported input type: {self.input_type}")

    def _process_cidemod(self):
        for key, value in self.input_data.items():
            if "kinetic_constant" in key:
                self.input_data[key] = value * 1e6
        return self.input_data

    def _process_battmo_m(self):
        # Save NE and PE porosities computed from volume fractions
        for elde in ["NegativeElectrode", "PositiveElectrode"]:
            coating = self.input_data.get(f"{elde}")
            vf = coating.get("volumeFraction")
            if vf is not None:
                porosity = 1.0 - vf
                if electrode == "negative_electrode":
                    self.input_data["NegativeElectrodeCoatingPorosity"] = porosity
                else:
                    self.input_data["PositiveElectrodeCoatingPorosity"] = porosity
        return self.input_data
