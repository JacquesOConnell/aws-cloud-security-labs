# AWS Control Tower Landing Zone Lab and Interview Guide

## Purpose

This guide documents a hands-on deployment of an AWS Control Tower 4.0 landing zone for a small personal cloud-security environment. It focuses on multi-account governance, centralized security services, identity, cost control, verification, and interview-ready explanations.

All identifiers, email addresses, portal URLs, and unredacted screenshots are intentionally excluded.

## Outcome

The implementation established:

- an AWS Organization operating with all features;
- a dedicated management account;
- `Security` and `Sandbox` organizational units (OUs);
- separate AWS Config aggregator and CloudTrail administrator accounts;
- centralized organization logging;
- IAM Identity Center access to all three accounts;
- automatic account enrollment;
- an AWS Control Tower baseline on the Sandbox OU;
- mandatory preventive controls; and
- cost alerts and short S3 log-retention policies.

## Architecture

```text
AWS Organization
|
+-- Management account
|   +-- AWS Control Tower landing zone
|   +-- AWS Organizations
|   +-- IAM Identity Center
|   +-- Account and control administration
|
+-- Security OU
|   +-- Personal Cloud Security Audit
|   |   +-- AWS Config organization aggregation
|   |
|   +-- Personal Cloud Log Archive
|       +-- Organization CloudTrail administration
|       +-- Centralized S3 log storage
|
+-- Sandbox OU
    +-- AWS Control Tower baseline
    +-- Automatic enrollment for future accounts
    +-- Preventive control inheritance
```

## Key design decisions

| Decision | Implementation | Reason |
|---|---|---|
| Home Region | Africa (Cape Town) | Kept governance close to the existing workload Region. |
| Governed Regions | One | Reduced AWS Config scope and cost for the personal environment. |
| Region deny | Disabled | Avoided interfering with existing global or cross-Region activity. |
| Security isolation | Two dedicated accounts | Separated compliance aggregation from immutable log storage. |
| Identity | IAM Identity Center managed by Control Tower | Provided temporary, multi-account SSO access. |
| Account enrollment | Automatic | Reduced manual enrollment and inheritance drift. |
| AWS Backup | Disabled | No centralized backup requirement existed for this lab. |
| Custom KMS encryption | Disabled | Avoided an unnecessary customer-managed key and recurring charge. |
| Primary log retention | 90 days | Balanced investigation value with personal-lab cost. |
| Access-log retention | 30 days | Limited secondary log growth. |
| Sandbox Config baseline | Deferred | The OU was empty, so detective recording would add cost without useful findings. |

## Implementation walkthrough

### 1. Secure administrative access

Before deploying the landing zone, direct `AdministratorAccess` was removed from the IAM user. Administration was moved behind an MFA-protected role. The Control Tower console was opened through that role rather than through the root user.

The intended human-access hierarchy is:

```text
Normal access:    IAM Identity Center -> permission set -> temporary role
Fallback access:  IAM user with MFA -> administrator role -> temporary role
Recovery access:  Root user -> root-only and account-recovery operations
```

### 2. Create the organization and OUs

Control Tower created a new AWS Organization and made the existing account its management account. It created:

- the foundational `Security` OU; and
- the recommended `Sandbox` OU.

In production, the management account should contain governance services rather than application workloads.

### 3. Configure AWS Config integration

AWS Config was enabled as a Control Tower service integration. A new account in the Security OU was designated as the organization aggregator for configuration and compliance data.

The Config integration enables detective controls when Config recording and relevant baselines are activated. An aggregator does not itself generate source configuration data; AWS Config must record resources in each governed source account and Region.

### 4. Configure centralized CloudTrail logging

A separate account in the Security OU was designated as the CloudTrail administrator and central log archive. Control Tower configured organization-level logging and centralized S3 storage.

This separation protects audit evidence from ordinary workload administrators and supports centralized investigation across accounts.

### 5. Configure retention and encryption

The lab used:

- 90-day primary log retention;
- 30-day access-log retention; and
- AWS-managed encryption rather than a customer-managed KMS key.

Production retention must be driven by legal, regulatory, security, and incident-response requirements. Longer retention would normally use lifecycle transitions to lower-cost archival storage.

### 6. Configure IAM Identity Center

Control Tower configured IAM Identity Center and sent an invitation for the initial user. After activation, the AWS access portal displayed:

- the management account;
- the log archive account; and
- the security audit account.

Initial permission sets included administrator access to the three accounts and Service Catalog end-user access in the management account. Production assignments should be narrowed with dedicated platform-administrator, security-auditor, incident-response, and log-viewer permission sets.

The portal's command-line credentials are temporary SSO credentials, not permanent IAM-user access keys.

### 7. Enable automatic enrollment

Automatic account enrollment was enabled after initial landing-zone deployment. When an account is moved into a registered OU, Control Tower can automatically apply that OU's baselines and controls, reducing manual work and inheritance drift.

### 8. Register the Sandbox OU

The Sandbox OU passed Control Tower pre-checks and was registered with the `AWSControlTowerBaseline`. Mandatory controls and required execution permissions were applied.

The OU was intentionally left empty. The `ConfigBaseline` was deferred until a workload account is available for a meaningful detective-control exercise.

## Verification

The following results were confirmed in the consoles:

- landing-zone version 4.0 was current;
- the landing-zone state was available;
- three AWS accounts were visible through IAM Identity Center;
- the audit and log archive accounts were active and compliant;
- centralized AWS Config and CloudTrail integrations were enabled;
- automatic account enrollment was turned on;
- the Sandbox Control Tower baseline was enabled;
- mandatory preventive controls were enabled; and
- AWS Backup and Region deny were not enabled.

## Control types

### Preventive controls

Preventive controls use mechanisms such as Service Control Policies (SCPs) to deny disallowed actions. They apply before an API action succeeds. An SCP is a permission boundary: it does not grant permissions and it cannot override an explicit deny.

### Detective controls

Detective controls evaluate deployed resources and report compliant or noncompliant states. They commonly depend on AWS Config recording and rule evaluations, so they can incur usage charges.

### Proactive controls

Proactive controls evaluate a proposed resource configuration before provisioning, commonly through CloudFormation hooks. They identify noncompliant definitions before deployment but are distinct from detective checks against existing resources.

## Control Tower, Organizations, and IAM

These services solve different problems:

- **AWS Organizations** provides the account hierarchy, consolidated billing, OUs, SCPs, and service integrations.
- **AWS Control Tower** orchestrates a governed landing zone, baselines, controls, account enrollment, and integrated services.
- **IAM Identity Center** provides centralized human access through users, groups, permission sets, and temporary role sessions.
- **IAM** continues to authorize actions within each AWS account.

## Cost considerations

AWS Control Tower and AWS Organizations do not have separate service fees, but the landing zone enables chargeable supporting services. Important cost sources include:

- AWS Config configuration items and rule evaluations;
- CloudTrail event recording;
- S3 log storage and requests;
- CloudWatch logs and metrics;
- SNS notifications; and
- resources provisioned through Account Factory.

Cost controls used in this lab included:

- one governed Region;
- an empty Sandbox OU;
- deferred Config recording for Sandbox;
- short log-retention policies;
- no custom KMS key;
- no AWS Backup integration; and
- a monthly AWS Budget with early actual and forecast alerts.

### Free-plan lesson

Under the newer AWS Free Tier account model, creating or joining an AWS Organization or deploying Control Tower automatically upgrades a Free Plan account to the paid plan. Promotional Free Tier credits may expire immediately. This must be checked before beginning a landing-zone lab.

New member-account welcome emails do not mean each account receives a separate promotional credit balance. The management account pays the consolidated organization bill.

## Security considerations

- Do not use root for normal Control Tower administration.
- Protect root identities and account mailboxes with MFA and recovery controls.
- Prefer IAM Identity Center and temporary credentials over long-lived IAM-user keys.
- Keep application workloads out of the management account in production.
- Restrict access to the log archive account.
- Separate audit access from platform administration.
- Do not manually modify Control Tower-managed resources without understanding drift.
- Do not publish account IDs, organization IDs, email addresses, access portal URLs, or unredacted logs.
- Use SCPs as organization-level boundaries, not as substitutes for IAM permissions.

## Limitations of this lab

- No dedicated workload account was provisioned in Sandbox.
- The Sandbox Config baseline was intentionally deferred.
- No optional detective or proactive control was evaluated against a workload.
- AWS Backup and customer-managed KMS encryption were not enabled.
- The management account contained pre-existing personal lab resources, which would not be recommended in a production landing zone.

These limitations are documented to distinguish completed work from planned extensions.

## Troubleshooting lessons

### Control Tower could not determine landing-zone state

The browser was still using the base IAM user after direct administrator access had been removed. An administrator role assumed in the CLI does not change the browser identity.

Resolution:

1. Sign out of the AWS Console.
2. Sign back in with the MFA-enabled IAM user.
3. Use **Switch Role** to enter the administrator role.
4. Reopen Control Tower in the intended home Region.

### Dashboard showed zero registered OUs

The foundational Security OU and shared accounts had been created, but the Sandbox workload OU had not yet been registered. Registering Sandbox enabled its Control Tower baseline.

### Automatic-enrollment banner remained visible

The dashboard briefly displayed stale state after the landing-zone update. The authoritative status was verified under Landing zone settings, where automatic account enrollment showed `Turned on`.

## Interview questions and answers

### What is AWS Control Tower?

AWS Control Tower is an orchestration service for establishing and governing a multi-account AWS landing zone. It integrates services such as AWS Organizations, IAM Identity Center, CloudTrail, AWS Config, CloudFormation, and Service Catalog, and applies standardized baselines and controls.

### Why use separate audit and log archive accounts?

The audit account centralizes security and compliance visibility, while the log archive account isolates organization logs from workload administrators. Separation reduces the chance that a compromised workload account can alter or delete security evidence.

### What is the difference between an IAM policy and an SCP?

An IAM policy grants or denies permissions to identities and resources within an account. An SCP defines the maximum available permissions for member accounts or OUs. An SCP never grants access; the principal still requires an IAM permission, and any applicable explicit deny wins.

### Why was only one Region governed?

The personal environment operated in one Region. Governing only that Region reduced AWS Config scope and cost. A production decision would account for resilience, data residency, regulatory requirements, threat exposure, and approved service locations.

### Why was the Sandbox Config baseline deferred?

The OU contained no workload accounts, so Config recording and detective evaluations would add cost without producing useful compliance results. The baseline can be enabled when a test workload account is introduced.

### How does automatic enrollment help?

It automatically applies the destination registered OU's baselines and controls when accounts are moved into that OU. This reduces manual enrollment and helps remediate control-inheritance drift.

### How would this design change for production?

Production would use a dedicated workload-free management account, separate production and non-production OUs, least-privilege permission sets, longer tiered log retention, formal break-glass access, delegated security administrators, broader governed Regions where required, and tested detective and proactive controls.

## Interview-ready project summary

> I deployed an AWS Control Tower 4.0 landing zone in a new AWS Organization. I configured Security and Sandbox OUs, separate accounts for centralized CloudTrail administration and AWS Config aggregation, IAM Identity Center multi-account access, automatic enrollment, mandatory preventive controls, and the Control Tower baseline on Sandbox. I limited governance to one Region and configured short log retention, no optional KMS key, and no AWS Backup to control cost. I deliberately deferred the Sandbox Config baseline because the OU had no workloads, and I documented how I would add detective controls in production.

## Evidence checklist

Before publishing evidence, redact:

- AWS account IDs;
- organization and OU IDs;
- email addresses;
- user names;
- access portal URLs;
- resource ARNs;
- billing details; and
- any authentication or invitation links.

Safe evidence can include:

- landing-zone version and status;
- counts of accounts and controls;
- anonymized OU hierarchy;
- enabled integration names;
- baseline status with identifiers hidden; and
- redacted IAM Identity Center account tiles.

## Decommissioning plan

Do not manually delete Control Tower-managed resources while the landing zone is active.

Recommended order:

1. Export required documentation and sanitized evidence.
2. Decommission the landing zone from Control Tower settings.
3. Wait for automated decommissioning to complete.
4. Review and remove residual S3 buckets and CloudWatch log groups.
5. Review AWS Config, CloudTrail, EventBridge, IAM roles, and Service Catalog artifacts.
6. Remove unneeded IAM Identity Center assignments, permission sets, groups, and users.
7. Retain empty member accounts for future labs or close them through AWS Organizations.
8. Remove empty OUs and delete the Organization only if multi-account use is no longer required.
9. Verify the Bills page and Cost Explorer until no unexpected usage remains.

Decommissioning does not automatically delete the Organization, OUs, member accounts, IAM Identity Center configuration, or every logging artifact.

## References

- [AWS Control Tower User Guide](https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html)
- [AWS Control Tower controls](https://docs.aws.amazon.com/controltower/latest/controlreference/introduction.html)
- [AWS Control Tower pricing](https://aws.amazon.com/controltower/pricing/)
- [AWS Config pricing](https://aws.amazon.com/config/pricing/)
- [AWS Control Tower decommissioning](https://docs.aws.amazon.com/controltower/latest/userguide/decommission-landing-zone.html)
- [AWS Organizations consolidated billing](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/consolidated-billing.html)
