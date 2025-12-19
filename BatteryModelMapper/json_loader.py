from pathlib import Path
from urllib.parse import urlparse
import json
import requests


class JSONLoader:
    @staticmethod
    def load(source):
        source = Path(source)

        if urlparse(str(source)).scheme in ("http", "https"):
            # Read from URL
            response = requests.get(str(source))
            response.raise_for_status()
            return response.json()
        elif source.is_file():
            # Read from file
            return json.loads(source.read_text(encoding="utf-8"))
        else:
            raise ValueError(f"File does not exist: {source}")
