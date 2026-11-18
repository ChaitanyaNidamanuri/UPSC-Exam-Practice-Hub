#!/usr/bin/env python3
"""
analyze_json_topics.py

Simple, reusable analysis for the question-bank JSON format used by
UPSC Exam Practice Hub.

Usage:
    python analyze_json_topics.py
    python analyze_json_topics.py "Pinnacle_GS/Pinnacle_GS_Complete.json"
    python analyze_json_topics.py "Pinnacle_GS/Pinnacle_GS_Complete.json" --field topic
    python analyze_json_topics.py "Pinnacle_GS/Pinnacle_GS_Complete.json" --field tag

The script:
- loads a JSON array (or common wrapper objects containing questions/data/items)
- reports question count
- reports available fields
- prints unique values and counts for the selected field
- also compares `topic` and `tag`, which is useful for deciding navigation fields
- writes a CSV report beside the JSON when --csv is supplied
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def extract_questions(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if isinstance(payload, dict):
        for key in ("questions", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]

        arrays = [v for v in payload.values() if isinstance(v, list)]
        if len(arrays) == 1:
            return [x for x in arrays[0] if isinstance(x, dict)]

    raise ValueError("Could not find a JSON question array.")


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def counts_for(questions: list[dict], field: str) -> Counter:
    values = [clean_value(q.get(field)) for q in questions]
    return Counter(v for v in values if v)


def print_field_report(questions: list[dict], field: str) -> None:
    counter = counts_for(questions, field)

    print(f"\n=== UNIQUE {field.upper()} VALUES ===")
    print(f"Unique non-empty values: {len(counter)}")

    if not counter:
        print("(none)")
        return

    for i, (value, count) in enumerate(counter.most_common(), 1):
        print(f"{i:>4}. {value}  [{count} questions]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze unique topic/tag values in a question-bank JSON.")
    parser.add_argument(
        "json_file",
        nargs="?",
        default="Pinnacle_GS/Pinnacle_GS_Complete.json",
        help="Path to the JSON file."
    )
    parser.add_argument(
        "--field",
        default="topic",
        choices=("topic", "tag"),
        help="Field whose unique values should be treated as candidate navigation topics."
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also write a CSV frequency report beside the JSON."
    )
    args = parser.parse_args()

    path = Path(args.json_file)
    if not path.exists():
        raise SystemExit(f"ERROR: File not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        questions = extract_questions(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}")

    print("=" * 72)
    print("JSON TOPIC ANALYSIS")
    print("=" * 72)
    print(f"File       : {path}")
    print(f"Questions  : {len(questions)}")

    fields = sorted({key for q in questions for key in q.keys()})
    print(f"Fields     : {', '.join(fields)}")

    topic_counts = counts_for(questions, "topic")
    tag_counts = counts_for(questions, "tag")

    print(f"\n`topic` unique values : {len(topic_counts)}")
    print(f"`tag` unique values   : {len(tag_counts)}")

    print_field_report(questions, args.field)

    # This comparison is deliberately included because `tag` often contains
    # exam/session metadata rather than conceptual subjects.
    if args.field == "topic":
        print("\nNOTE:")
        if len(topic_counts) < len(tag_counts):
            print(
                "The JSON has fewer unique `topic` values than `tag` values. "
                "Inspect the printed tag values before using `tag` as UI topics."
            )
        else:
            print("The `topic` field is the selected navigation field.")
    else:
        print("\nNOTE:")
        print(
            "You selected `tag`. Verify that these values are actual subjects/topics "
            "before using them as navigation cards."
        )

    if args.csv:
        output = path.with_name(path.stem + f"_{args.field}_analysis.csv")
        counter = counts_for(questions, args.field)
        with output.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["rank", args.field, "question_count"])
            for rank, (value, count) in enumerate(counter.most_common(), 1):
                writer.writerow([rank, value, count])
        print(f"\nCSV report : {output}")


if __name__ == "__main__":
    main()
