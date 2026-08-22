# implements: eval harness for OCR confidence tuning (post-D-022 baseline, extends D-007)
"""Reports OCR confidence distribution from a pipeline logs.csv, to help tune
pipeline.ocr.LOW_CONFIDENCE_THRESHOLD against real run data.

Usage:
    python -m pipeline.eval_confidence --csv output/logs.csv
"""

import argparse
import csv
import statistics

from pipeline.ocr import LOW_CONFIDENCE_THRESHOLD


def load_confidences(csv_path: str) -> list[float]:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return [float(row["ocr_confidence"]) for row in reader]


def summarize(confidences: list[float], threshold: float = LOW_CONFIDENCE_THRESHOLD) -> dict:
    if not confidences:
        return {"count": 0}
    below = sum(1 for c in confidences if c < threshold)
    return {
        "count": len(confidences),
        "mean": statistics.mean(confidences),
        "median": statistics.median(confidences),
        "min": min(confidences),
        "max": max(confidences),
        "below_threshold": below,
        "below_threshold_pct": 100 * below / len(confidences),
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize OCR confidence from a pipeline logs.csv")
    parser.add_argument("--csv", default="output/logs.csv")
    parser.add_argument("--threshold", type=float, default=LOW_CONFIDENCE_THRESHOLD)
    args = parser.parse_args()

    confidences = load_confidences(args.csv)
    stats = summarize(confidences, args.threshold)

    if stats["count"] == 0:
        print(f"No rows found in {args.csv}")
        return

    print(f"Rows:                {stats['count']}")
    print(f"Mean confidence:     {stats['mean']:.3f}")
    print(f"Median confidence:   {stats['median']:.3f}")
    print(f"Min / Max:           {stats['min']:.3f} / {stats['max']:.3f}")
    print(f"Below threshold {args.threshold}: {stats['below_threshold']} ({stats['below_threshold_pct']:.1f}%)")


if __name__ == "__main__":
    main()
