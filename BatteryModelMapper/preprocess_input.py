class PreprocessInput:
    def __init__(self, input_type, input_data):
        """Store the input format and JSON-like data to be normalized before mapping."""
        self.input_type = input_type
        self.input_data = input_data

    def process(self):
        """Run the preprocessing routine for the configured input format."""
        if self.input_type == "cidemod":
            return self._process_cidemod()
        elif self.input_type == "battmo.m":
            return self._process_battmo_m()
        else:
            raise ValueError(f"Unsupported input type: {self.input_type}")

    def _process_cidemod(self):
        """Scale CIDEMOD kinetic constants into the units expected by the mapper."""
        # Scale kinetic constant
        for key, value in self.input_data.items():
            if "kinetic_constant" in key:
                self.input_data[key] = value * 1e6
        return self.input_data

    def _process_battmo_m(self):
        """Compute BattMo electrode coating porosities from active material fractions."""
        # Save NE and PE porosities computed from volume fractions
        eldes = ["NegativeElectrode", "PositiveElectrode"]
        for elde in eldes:
            elde_data = self.input_data.get(elde)
            co_data = elde_data.get("Coating")
            vf = co_data.get("volumeFraction")
            if vf is None:
                raise ValueError(f"Missing volumeFraction data for {elde}")
            else:
                porosity = 1.0 - vf
                self.input_data[elde]["Coating"]["porosity"] = porosity

        return self.input_data
