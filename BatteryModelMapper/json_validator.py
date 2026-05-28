from jsonschema import validate, ValidationError
from .json_loader import JSONLoader

class JSONValidator:
    @staticmethod
    def validate(data, schema_url):
        """Validate JSON-like data against a schema loaded from a file or URL."""
        schema = JSONLoader.load(schema_url)
        try:
            validate(instance=data, schema=schema)
            print("JSON is valid.")
        except ValidationError as e:
            print(f"JSON validation error: {e.message}")
            raise
