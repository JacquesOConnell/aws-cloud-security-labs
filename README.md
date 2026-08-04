# AWS Cloud Security Labs

Hands-on AWS security labs focused on practical engineering, troubleshooting and interview-ready explanations.

## Completed labs

### AWS CloudHSM

- Deployed a FIPS-mode CloudHSM cluster and EC2 client.
- Verified AWS and manufacturer hardware certificate chains.
- Created a customer-controlled root CA and initialized the cluster.
- Activated the cluster and implemented HSM user separation of duties.
- Generated non-exportable AES and RSA keys inside the HSM.
- Completed HSM-backed RSA signing and verification.
- Documented the single-HSM lab exception and production multi-AZ design.

Read the [CloudHSM Lab and Interview Guide](cloudhsm/AWS-CloudHSM-Lab-and-Interview-Guide.md).

### AWS KMS BYOK and imported key material

- Created an external-origin symmetric KMS key.
- Generated 256-bit AES material outside AWS.
- Wrapped the material with RSA-4096 and RSA-OAEP SHA-256.
- Imported the material and tested encryption contexts.
- Demonstrated cryptographic erasure by deleting the imported material.
- Reimported the identical material and restored access to existing ciphertext.
- Audited the lifecycle using AWS CloudTrail.
- Documented key custody, durability, rotation and production controls.

Read the [AWS KMS BYOK Lab and Interview Guide](kms-byok/AWS-KMS-BYOK-Lab-and-Interview-Guide.md).

### Python AWS Security Posture Auditor

- Built a read-only Python and Boto3 security posture auditor.
- Added IAM checks for missing MFA, aged access keys and excessive permissions.
- Added KMS checks for key state, rotation and imported key material.
- Produced normalized console, JSON and CSV findings.
- Enforced execution through a dedicated read-only audit role.
- Added unit tests with mocked AWS API responses.

Read the [Security Posture Auditor guide](python-security-posture-auditor/README.md).

### AWS Control Tower landing zone

- Deployed an AWS Control Tower 4.0 landing zone.
- Created Security and Sandbox organizational units.
- Separated AWS Config aggregation and centralized CloudTrail logging into dedicated accounts.
- Configured IAM Identity Center for temporary multi-account SSO access.
- Enabled automatic account enrollment and registered the Sandbox OU.
- Applied mandatory preventive controls and documented detective-control cost tradeoffs.
- Added cost alerts and short log-retention policies.

Read the [AWS Control Tower Landing Zone Lab and Interview Guide](control-tower/AWS-Control-Tower-Landing-Zone-Lab-and-Interview-Guide.md).

## Planned labs

- Additional S3, EC2 security group and CloudTrail auditor modules

## Security notice

This repository contains documentation and sanitized examples only. It must never contain private keys, credentials, live certificates, Terraform state, account IDs, public hostnames, private IP addresses or unredacted command output.

## Disclaimer

These labs are personal learning environments. Production deployments require formal architecture review, high availability, monitoring, backup and recovery testing, least privilege, approved key custody and organizational security controls.
