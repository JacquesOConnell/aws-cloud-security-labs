import argparse
from pathlib import Path

import boto3

from .iam_checks import audit_iam
from .kms_checks import audit_kms
from .reporting import print_summary, write_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run read-only AWS security posture checks."
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        default=["af-south-1"],
        help="AWS Regions to audit (default: af-south-1).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory for JSON and CSV reports.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = boto3.Session()

    caller = session.client("sts").get_caller_identity()
    caller_arn = caller["Arn"]
    if ":assumed-role/SecurityAuditLabRole/" not in caller_arn:
        raise RuntimeError(
            "Refusing to run: assume SecurityAuditLabRole before starting the auditor."
        )

    findings = []
    findings.extend(audit_iam(session.client("iam")))
    for region in args.regions:
        findings.extend(audit_kms(session.client("kms", region_name=region), region))

    print_summary(findings)
    json_path, csv_path = write_reports(findings, args.output_dir)
    print(f"\nJSON report: {json_path}")
    print(f"CSV report:  {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

