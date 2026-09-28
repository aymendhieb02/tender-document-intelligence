"""Run with: python -m app.cdc_analysis document_result.json --output tender.json"""
import argparse
import json
from pathlib import Path

from .pipeline import CDCAnalyzer
from .benchmark import evaluate


def main():
    parser = argparse.ArgumentParser(description="Analyze a CDC consumer-contract JSON (not a PDF)")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Prediction output must not overwrite the source input")
    if args.ground_truth and args.ground_truth.resolve() == args.output.resolve():
        parser.error("Prediction output must not overwrite ground truth")
    if "ground_truth" in {part.casefold() for part in args.output.resolve().parts}:
        parser.error("Prediction output must be stored separately from the ground_truth directory")
    result = CDCAnalyzer().analyze(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if args.ground_truth:
        print(json.dumps(evaluate(result, json.loads(args.ground_truth.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
