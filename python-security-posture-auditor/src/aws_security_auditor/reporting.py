import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .models import Finding


FIELDNAMES = [
    "severity",
    "service",
    "region",
    "resource",
    "check_id",
    "title",
    "status",
    "evidence",
    "recommendation",
]


def write_reports(findings: list[Finding], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    rows = [finding.to_dict() for finding in findings]

    json_path = output_dir / f"aws-security-findings-{timestamp}.json"
    csv_path = output_dir / f"aws-security-findings-{timestamp}.csv"

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return json_path, csv_path


def print_summary(findings: list[Finding]) -> None:
    counts = Counter(finding.severity for finding in findings)
    print("\nAWS Security Posture Auditor")
    print("=" * 30)
    print(f"Total findings: {len(findings)}")
    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        print(f"{severity:8}: {counts.get(severity, 0)}")

    for finding in findings:
        print(
            f"\n[{finding.severity}] {finding.check_id} | "
            f"{finding.region} | {finding.resource}"
        )
        print(f"  {finding.title}")
        print(f"  Evidence: {finding.evidence}")


