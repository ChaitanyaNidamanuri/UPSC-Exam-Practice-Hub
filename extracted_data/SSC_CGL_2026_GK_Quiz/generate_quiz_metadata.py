#!/usr/bin/env python3
"""
Generate quiz-bank metadata JSON files from question-bank JSON files.

Metadata schema:
{
  "schemaVersion": 1,
  "bankKey": "example_bank",
  "totalCount": 100,
  "topicCount": 2,
  "topics": [
    {
      "name": "Polity",
      "count": 60,
      "subtopics": [
        {"name": "Constitution", "count": 25}
      ]
    }
  ]
}

By default, each output is written beside its source file as:
    <source filename without extension>_METADATA.json

Examples:
    python generate_metadata.py SSC_CGL_2026_GK_Quiz.json
    python generate_metadata.py bank1.json bank2.json
    python generate_metadata.py ./extracted_data --recursive
    python generate_metadata.py SSC_CGL_2026_GK_Quiz.json --bank-key ssc_cgl_2026_gk
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


def clean_name(value: Any, field: str, question_number: int) -> str:
    """Return a trimmed category name, using a visible fallback if absent."""
    if value is None:
        return "Uncategorized"
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value if value else "Uncategorized"


def make_bank_key(source: Path) -> str:
    """Convert a filename into a predictable lowercase snake_case bank key."""
    name = source.stem
    name = re.sub(r"[^A-Za-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower() or "quiz_bank"


def build_metadata(questions: list[dict[str, Any]], bank_key: str) -> dict[str, Any]:
    """
    Count questions by topic and subtopic, preserving the first-seen order
    from the source JSON. Every question is counted exactly once.
    """
    topic_groups: OrderedDict[str, OrderedDict[str, int]] = OrderedDict()

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError(
                f"Question at array position {index} is not a JSON object."
            )

        topic = clean_name(question.get("topic"), "topic", index)
        subtopic = clean_name(question.get("subtopic"), "subtopic", index)

        if topic not in topic_groups:
            topic_groups[topic] = OrderedDict()

        topic_groups[topic][subtopic] = topic_groups[topic].get(subtopic, 0) + 1

    topics = []
    for topic_name, subtopic_counts in topic_groups.items():
        subtopics = [
            {"name": subtopic_name, "count": count}
            for subtopic_name, count in subtopic_counts.items()
        ]
        topics.append({
            "name": topic_name,
            "count": sum(subtopic_counts.values()),
            "subtopics": subtopics,
        })

    metadata = {
        "schemaVersion": 1,
        "bankKey": bank_key,
        "totalCount": len(questions),
        "topicCount": len(topics),
        "topics": topics,
    }

    # Internal consistency checks before writing.
    topic_total = sum(topic["count"] for topic in topics)
    subtopic_total = sum(
        subtopic["count"]
        for topic in topics
        for subtopic in topic["subtopics"]
    )
    if topic_total != len(questions) or subtopic_total != len(questions):
        raise RuntimeError("Metadata count validation failed.")

    return metadata


def load_questions(source: Path) -> list[dict[str, Any]]:
    try:
        with source.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {source}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc

    # Accept either a plain array or a wrapper object containing a question array.
    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict):
        questions = None
        for key in ("questions", "data", "items"):
            if isinstance(data.get(key), list):
                questions = data[key]
                break
        if questions is None:
            raise ValueError(
                f"{source} contains a JSON object, but no question array was "
                "found under 'questions', 'data' or 'items'."
            )
    else:
        raise ValueError(
            f"{source} must contain a JSON array or an object wrapping a question array."
        )

    if not questions:
        raise ValueError(f"No questions found in {source}.")
    return questions


def process_file(source: Path, bank_key: str | None = None,
                 output_dir: Path | None = None) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input JSON file not found: {source}")

    questions = load_questions(source)
    key = bank_key or make_bank_key(source)
    metadata = build_metadata(questions, key)

    destination_dir = output_dir.resolve() if output_dir else source.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source.stem}_METADATA.json"

    with destination.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return destination


def find_json_files(paths: list[str], recursive: bool) -> list[Path]:
    found: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_file():
            if path.suffix.lower() == ".json" and not path.stem.endswith("_METADATA"):
                found.append(path)
        elif path.is_dir():
            iterator = path.rglob("*.json") if recursive else path.glob("*.json")
            found.extend(
                item for item in iterator
                if item.is_file() and not item.stem.endswith("_METADATA")
            )
        else:
            print(f"WARNING: Skipping missing path: {path}", file=sys.stderr)

    # Deduplicate while preserving order.
    unique: list[Path] = []
    seen: set[str] = set()
    for item in found:
        identity = str(item.resolve()).lower()
        if identity not in seen:
            seen.add(identity)
            unique.append(item)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate _METADATA.json files from quiz question-bank JSON files."
    )
    parser.add_argument(
        "inputs", nargs="+",
        help="One or more question JSON files or folders containing JSON files."
    )
    parser.add_argument(
        "--recursive", action="store_true",
        help="Search input folders recursively for JSON files."
    )
    parser.add_argument(
        "--bank-key",
        help="Override bankKey. Use this only when processing one input file."
    )
    parser.add_argument(
        "--output-dir", type=Path,
        help="Write generated metadata into this folder instead of beside each source."
    )
    args = parser.parse_args()

    sources = find_json_files(args.inputs, args.recursive)
    if not sources:
        print("ERROR: No question-bank JSON files found.", file=sys.stderr)
        return 1

    if args.bank_key and len(sources) != 1:
        print("ERROR: --bank-key can only be used with one input JSON file.", file=sys.stderr)
        return 1

    failures = 0
    for source in sources:
        try:
            destination = process_file(source, args.bank_key, args.output_dir)
            with destination.open("r", encoding="utf-8") as file:
                metadata = json.load(file)
            print(
                f"OK  {source.name} -> {destination}\n"
                f"    Questions: {metadata['totalCount']:,} | "
                f"Topics: {metadata['topicCount']} | "
                f"Subtopics: {sum(len(t['subtopics']) for t in metadata['topics'])}"
            )
        except Exception as exc:
            failures += 1
            print(f"ERROR processing {source}: {exc}", file=sys.stderr)

    print(f"\nFinished: {len(sources) - failures} succeeded, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
