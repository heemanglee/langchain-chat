"""FastAPI 앱에서 openapi.json을 생성하는 스크립트."""

import json
from pathlib import Path

from app.main import app


def main() -> None:
    schema = app.openapi()
    output = Path("openapi.json")
    output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    print(f"Generated {output} ({len(schema['paths'])} endpoints)")


if __name__ == "__main__":
    main()
