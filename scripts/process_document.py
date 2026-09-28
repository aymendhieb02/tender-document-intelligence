"""Extract local generic document evidence; does not run any business extractor."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.document_intelligence import DocumentProcessor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--mode", choices=("auto", "native", "ocr", "hybrid"), default="auto")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = DocumentProcessor(mode=args.mode, use_cache=not args.no_cache,
                               allow_fallback=not args.no_fallback).process(args.document)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"{len(result.pages)} pages; {sum(len(p.elements) for p in result.pages)} elements; "
          f"{result.diagnostics.processing_ms:.0f} ms")


if __name__ == "__main__":
    main()
