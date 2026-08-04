# AWS Security Posture Auditor

A read-only Python and Boto3 project that audits AWS security configuration and produces normalized console, JSON and CSV findings.

## Current checks

The current implementation audits AWS KMS and IAM:

- keys that are not enabled;
- eligible customer-managed keys without automatic rotation;
- external-origin keys that require custody and reimport review.
- console users without MFA;
- active access keys older than 90 days;
- direct or group-based AdministratorAccess;
- inline user policies requiring review.

Future modules will cover S3, EC2 security groups and CloudTrail.

## Security model

The auditor refuses to run unless the active identity is an assumed session of `SecurityAuditLabRole`. The role uses the AWS-managed `SecurityAudit` policy. No credentials are stored in this repository.

Generated reports are ignored because they can contain live AWS resource identifiers.

## Run tests

```powershell
$env:PYTHONPATH = "$PWD\src"
pytest -q
```

## Run the KMS audit

Assume `SecurityAuditLabRole`, load its temporary credentials into the current PowerShell process, and run:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m aws_security_auditor.cli --regions af-south-1
```

Reports are written into `reports/` and must be reviewed and sanitized before sharing.

