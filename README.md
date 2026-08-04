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

## Planned labs

- AWS KMS imported key material (BYOK)
- AWS Control Tower security guardrails and account governance
- Python/boto3 security automation

## Security notice

This repository contains documentation and sanitized examples only. It must never contain private keys, credentials, live certificates, Terraform state, account IDs, public hostnames, private IP addresses or unredacted command output.

## Disclaimer

These labs are personal learning environments. Production deployments require formal architecture review, high availability, monitoring, backup and recovery testing, least privilege, approved key custody and organizational security controls.
