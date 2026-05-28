import json

class JSONWriter:
    @staticmethod
    def write(data, output_path):
        """Write JSON-serializable data to a file with readable indentation."""
        with open(output_path, 'w') as file:
            json.dump(data, file, indent=4)
