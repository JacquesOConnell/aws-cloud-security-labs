# Security and sanitization policy

This repository contains learning material and sanitized examples. It must not contain live credentials, private key material, HSM passwords, account-specific identifiers, or Terraform state.

## Never commit

- AWS access keys, session tokens, profiles, or credential files
- Private keys, including SSH, CA, TLS, PKCS #12, or HSM backup material
- HSM administrator or crypto-user passwords
- Live account IDs, cluster IDs, hostnames, IP addresses, or resource ARNs
- Terraform state, variable files containing secrets, or provider credentials
- Unredacted command output or screenshots

The root `.gitignore` blocks common sensitive file formats, but it is only a safety net. Review every staged change before pushing.

## Pre-push check

```powershell
git status
git diff --cached
```

If a secret was committed, rotate or revoke it immediately. Removing it from the latest file does not remove it from Git history.

## Lab cleanup

Cloud security labs can create billable resources. Delete temporary HSMs, clusters, EC2 instances, storage, and networking components after capturing evidence and confirming their dependencies.
