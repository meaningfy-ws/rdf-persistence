"""Write the toy service's OpenAPI document to the path given, for the TypeScript check (make typecheck-openapi-ts)."""

import json
import sys
from pathlib import Path

from tests.toy_service import ToyService


def main(target: str) -> None:
    Path(target).write_text(json.dumps(ToyService().app.openapi(), indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
