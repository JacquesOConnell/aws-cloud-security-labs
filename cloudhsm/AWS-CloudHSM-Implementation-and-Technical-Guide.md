# AWS CloudHSM Implementation and Technical Guide

**Prepared for:** Jacques O'Connell  
**Lab date:** 4 August 2026  
**Region:** `af-south-1` (Africa - Cape Town)  
**Cluster:** `<redacted>`  
**Mode and type:** FIPS, `hsm2m.medium`  
**Purpose:** Repeatable hands-on lab, implementation record, and technical reference

> **Achievement statement:** I deployed, initialized and activated an AWS CloudHSM cluster in FIPS mode. I verified the first HSM through independent AWS and Marvell certificate chains, created a customer-controlled root CA, signed the cluster CSR, configured an EC2 CloudHSM client, established separate administrator and crypto-user roles, generated non-exportable symmetric and asymmetric keys inside the HSM, and completed an HSM-backed RSA signing and verification test.

## 1. Executive summary

AWS CloudHSM provides single-tenant hardware security modules under customer control. AWS manages the physical appliances, availability and integration with the AWS control plane, but the customer controls HSM users, credentials and cryptographic key material. CloudHSM is appropriate when an organization needs dedicated HSMs, PKCS #11/JCE/OpenSSL integration, specific cryptographic mechanisms, or direct control that AWS KMS does not provide.

This lab exercised the complete lifecycle:

1. Created a FIPS-mode CloudHSM cluster and its first HSM.
2. Launched an Amazon Linux 2023 EC2 client in the same VPC.
3. Installed CloudHSM CLI 5.17.2.
4. Created a customer root CA outside AWS CloudHSM.
5. Verified the HSM's AWS and manufacturer trust chains.
6. Confirmed the Cluster CSR belonged to that verified HSM.
7. Signed the Cluster CSR and initialized the cluster.
8. Configured the client and activated the cluster.
9. Created an HSM crypto user, separate from the administrator.
10. Generated non-exportable AES and RSA keys inside the HSM.
11. Signed and verified data using the HSM-resident RSA key.

## 2. What CloudHSM solves

CloudHSM is designed for workloads that require dedicated HSM capacity and direct cryptographic interfaces. Typical use cases include private certificate authorities, database encryption, payment cryptography, document signing, code signing, TLS private-key protection and application integration through PKCS #11, JCE or OpenSSL.

### CloudHSM compared with AWS KMS

| Dimension | AWS KMS | AWS CloudHSM |
|---|---|---|
| Operating model | Fully managed key-management service | Customer-controlled, single-tenant HSM cluster |
| Interfaces | AWS APIs and integrated AWS services | PKCS #11, JCE, OpenSSL and CloudHSM tooling |
| HSM tenancy | Multi-tenant service backed by validated HSMs | Dedicated HSM instances |
| User administration | IAM and KMS key policies | IAM for infrastructure; HSM-native users for cryptographic access |
| Operational effort | Low | Higher: networking, users, client software, HA and backups |
| Best fit | General AWS encryption and envelope encryption | Regulatory, interoperability or dedicated-control requirements |

**Decision principle:** Prefer KMS unless a requirement specifically needs dedicated HSMs, customer-managed HSM users, unsupported algorithms/interfaces, or direct application access through industry-standard crypto APIs.

## 3. Architecture

```text
Administrator workstation
  |-- AWS CLI / AWS console: manages the CloudHSM service
  |-- OpenSSL: creates the customer CA and signs the Cluster CSR
  |
  +--> AWS account, af-south-1
        |
        +--> VPC
              |-- EC2 CloudHSM client (Amazon Linux 2023)
              |     |-- CloudHSM CLI 5.17.2
              |     `-- customerRootCA.crt trust anchor
              |
              `-- CloudHSM cluster (FIPS, hsm2m.medium)
                    `-- HSM ENI: <hsm-private-ip>
```

The EC2 client communicates with the HSM through private VPC networking. The HSM is not administered using its public internet endpoint. AWS IAM authorizes control-plane actions such as creating and deleting clusters; HSM-native credentials authorize user and cryptographic operations inside the device.

## 4. The certificate model - the essential explanation

The lab used two independent trust processes. Mixing these processes is the main source of confusion.

### 4.1 Hardware authenticity verification

AWS and Marvell certificates answered:

> Did this CSR originate from genuine Marvell hardware operating as an AWS CloudHSM?

```text
AWS CloudHSM Root ----------------> AWS Hardware Certificate ----+
                                                              |
Marvell RSA Root -----------------> Manufacturer Certificate ---+--> HSM Certificate
                                                                        |
                                                                        +-- same public key --> Cluster CSR
```

### 4.2 Customer ownership

The customer CA answered:

> Which customer has claimed and controls this cluster?

```text
customerRootCA.key (private, encrypted, never uploaded)
          |
          +--> customerRootCA.crt (public trust anchor)
          |
          `--> signs Cluster CSR --> CustomerHsmCertificate.crt
```

### 4.3 Certificate and key inventory

| File | Issuer / owner | Purpose | Sensitive? |
|---|---|---|---|
| `AWS_CloudHSM_Root-G1.crt` | AWS | Root of the AWS hardware-attestation chain | No |
| `*_AwsHardwareCertificate.crt` | AWS | Attests that AWS owns/operates the hardware | No |
| `mrvl-rsa-LS2-AR-v1.crt` | Marvell | Root of the manufacturer chain for the HSM type | No |
| `*_ManufacturerHardwareCertificate.crt` | Marvell | Attests that Marvell manufactured the hardware | No |
| `*_HsmCertificate.crt` | HSM, certified through hardware chains | Identity certificate generated by the HSM | No |
| `*_ClusterCsr.csr` | First HSM | Request for the customer's ownership certificate | No |
| `customerRootCA.key` | Customer | Encrypted CA private key used to sign the CSR | **Yes - critical** |
| `customerRootCA.crt` | Customer | Public CA certificate distributed to CloudHSM clients | No |
| `*_CustomerHsmCertificate.crt` | Customer CA | Signed cluster identity used during initialization | No |
| `customerRootCA.srl` | OpenSSL | Tracks issued-certificate serial numbers | No |

**Memory anchor:** AWS and Marvell certificates verified the hardware; the customer root CA established customer ownership.

## 5. Lab prerequisites and security decisions

- AWS account with permissions to administer CloudHSM, EC2, VPC and security groups.
- Region `af-south-1`.
- VPC and subnet for the HSM and EC2 client.
- Security-group connectivity between the EC2 client and CloudHSM cluster.
- Amazon Linux 2023 EC2 instance.
- OpenSSL on the local workstation (Git for Windows OpenSSL 3.5.7 was used).
- AWS CloudHSM CLI 5.17.2 on EC2.
- A cost-control plan: one HSM for a short lab, then immediate deletion.

For the lab, a single HSM was deliberately used to control cost. Production clusters should use multiple HSMs across Availability Zones. Client SDK 5's key-availability quorum was disabled only because the single-HSM lab could not replicate a key to a second HSM.

## 6. Detailed implementation steps

### Step 1 - Create the cluster

In the AWS CloudHSM console, create a cluster with:

- Mode: FIPS
- HSM type: `hsm2m.medium`
- Network: IPv4
- Region: Africa (Cape Town)
- VPC and subnets selected for the lab

The resulting cluster ID was `<cluster-id>`.

### Step 2 - Create the EC2 client

Launch an Amazon Linux 2023 `t3.micro` client in the same VPC. Permit SSH only from the administrator's current public IP. Associate the CloudHSM cluster security group as required for client-to-HSM connectivity.

Windows OpenSSH rejected the private key because its ACL was too broad. The permissions were restricted so only the current user could read the PEM file, after which SSH succeeded.

```powershell
ssh -i "C:\Users\<username>\Downloads\<key-pair>.pem" `
  ec2-user@<ec2-public-dns>
```

### Step 3 - Install CloudHSM CLI

On EC2:

```bash
wget https://s3.amazonaws.com/cloudhsmv2-software/CloudHsmClient/Amzn2023/cloudhsm-cli-latest.amzn2023.x86_64.rpm
sudo yum install -y ./cloudhsm-cli-latest.amzn2023.x86_64.rpm
/opt/cloudhsm/bin/cloudhsm-cli --version
```

Installed version: `cloudhsm-cli 5.17.2`.

The initial download stalled while connecting to Amazon S3. Checking the client's outbound routing/security configuration resolved the issue.

### Step 4 - Create the customer root CA

Workstation folder:

```text
C:\Users\<username>\Documents\CloudHSM-Lab
```

Generate an encrypted 3072-bit RSA private key:

```powershell
$OpenSSL = "C:\Program Files\Git\usr\bin\openssl.exe"
& $OpenSSL genrsa -aes256 -out customerRootCA.key 3072
```

Create a self-signed CA certificate with critical CA constraints and signing usage:

```powershell
& $OpenSSL req -new -x509 -sha256 -days 3650 `
  -key customerRootCA.key `
  -out customerRootCA.crt `
  -addext "basicConstraints=critical,CA:TRUE" `
  -addext "keyUsage=critical,keyCertSign,cRLSign"
```

The subject was:

```text
C=ZA, ST=Gauteng, L=Benoni, O=Personal Cloud Security Lab,
OU=CloudHSM, CN=CloudHSM Lab Root CA
```

Verify it:

```powershell
& $OpenSSL x509 -in customerRootCA.crt -noout -subject -issuer -dates
```

Because subject and issuer match, this certificate is self-signed. In production, create and protect the CA key using an offline HSM or an approved enterprise PKI process.

### Step 5 - Create the first HSM and download identity material

Create the first HSM in the cluster. Before initialization, download:

- Cluster CSR
- HSM certificate
- AWS hardware certificate
- Manufacturer hardware certificate

Hardware verification is optional, but it can only be completed before initialization.

Also download and extract:

- AWS CloudHSM Root G1 certificate
- Marvell LiquidSecurity2 manufacturer roots

The scripted Marvell download returned `Access Denied`, so the certificate archive was downloaded through Marvell's browser page instead.

### Step 6 - Select the correct manufacturer root

Inspect the manufacturer certificate issuer:

```powershell
& $OpenSSL x509 `
  -in "<cluster-id>_ManufacturerHardwareCertificate.crt" `
  -noout -issuer
```

The issuer contained `CN=mrvl-ls2-root-AR-v1`, matching the RSA root:

```text
mrvl-rsa-LS2-AR-v1.crt
```

### Step 7 - Verify the AWS hardware chain

Build the chain in leaf-to-root order:

```powershell
cmd /c copy /b `
  "<cluster-id>_AwsHardwareCertificate.crt+AWS_CloudHSM_Root-G1.crt" `
  "<cluster-id>_AWS_chain.crt"
```

Verify the HSM certificate:

```powershell
& $OpenSSL verify `
  -CAfile "<cluster-id>_AWS_chain.crt" `
  "<cluster-id>_HsmCertificate.crt"
```

Expected result: `OK`.

### Step 8 - Verify the manufacturer hardware chain

```powershell
cmd /c copy /b `
  "<cluster-id>_ManufacturerHardwareCertificate.crt+mrvl-rsa-LS2-AR-v1.crt" `
  "<cluster-id>_manufacturer_chain.crt"

& $OpenSSL verify `
  -CAfile "<cluster-id>_manufacturer_chain.crt" `
  "<cluster-id>_HsmCertificate.crt"
```

Expected result: `OK`.

Together, the two successful checks established independent AWS and manufacturer attestation of the HSM.

### Step 9 - Prove the CSR came from that HSM

Extract the public keys:

```powershell
& $OpenSSL x509 `
  -in "<cluster-id>_HsmCertificate.crt" `
  -pubkey -noout |
  Set-Content "<cluster-id>_HsmCertificate.pub" -Encoding ascii

& $OpenSSL req `
  -in "<cluster-id>_ClusterCsr.csr" `
  -pubkey -noout |
  Set-Content "<cluster-id>_ClusterCsr.pub" -Encoding ascii

Get-FileHash `
  "<cluster-id>_HsmCertificate.pub", `
  "<cluster-id>_ClusterCsr.pub" `
  -Algorithm SHA256
```

The hashes matched. Therefore, the Cluster CSR contained the same public key as the independently verified HSM certificate.

### Step 10 - Sign the Cluster CSR

```powershell
& $OpenSSL x509 -req -sha256 -days 3650 `
  -in "<cluster-id>_ClusterCsr.csr" `
  -CA "customerRootCA.crt" `
  -CAkey "customerRootCA.key" `
  -CAcreateserial `
  -out "<cluster-id>_CustomerHsmCertificate.crt"
```

Verify the result:

```powershell
& $OpenSSL verify -purpose sslserver `
  -CAfile "customerRootCA.crt" `
  "<cluster-id>_CustomerHsmCertificate.crt"
```

Expected result: `OK`.

The CA private key remained local and was never uploaded to AWS.

### Step 11 - Initialize the cluster

In the console initialization wizard, upload:

- **Cluster certificate:** `<cluster-id>_CustomerHsmCertificate.crt`
- **Issuing certificate:** `customerRootCA.crt`

Never upload `customerRootCA.key`.

After initialization, the cluster state became `INITIALIZED`. Initialization claims the cluster by establishing the customer's certificate trust anchor; it does not yet set the first administrator password.

### Step 12 - Configure the EC2 client

The HSM ENI private address was `<hsm-private-ip>`.

Copy the public customer CA certificate to EC2:

```powershell
scp -i "C:\Users\<username>\Downloads\<key-pair>.pem" `
  "C:\Users\<username>\Documents\CloudHSM-Lab\customerRootCA.crt" `
  ec2-user@<ec2-public-dns>:/home/ec2-user/
```

On EC2:

```bash
sudo cp /home/ec2-user/customerRootCA.crt /opt/cloudhsm/etc/customerRootCA.crt
sudo chmod 644 /opt/cloudhsm/etc/customerRootCA.crt
sudo /opt/cloudhsm/bin/configure-cli -a <hsm-private-ip>
sudo /opt/cloudhsm/bin/configure-cli \
  --hsm-ca-cert /opt/cloudhsm/etc/customerRootCA.crt
cat /opt/cloudhsm/etc/cloudhsm-cli.cfg
```

The client received only the public CA certificate, not the CA private key.

### Step 13 - Activate the cluster

```bash
/opt/cloudhsm/bin/cloudhsm-cli interactive
```

For Client SDK 5.17.2, the correct grouped information command is:

```text
cluster hsm-info
```

The earlier `hsm-info` command failed because it omitted the `cluster` command group.

List initial users:

```text
user list
```

The initial administrator had the temporary `unactivated-admin` role. Activate the cluster:

```text
cluster activate
```

The prompted password became the first HSM administrator password. After activation, `user list` showed the permanent `admin` role and the AWS console cluster state became `ACTIVE`.

### Step 14 - Create a crypto user

```text
login --username admin --role admin
user create --username crypto_user --role crypto-user
user list
```

The crypto-user password was entered interactively and was not stored in shell history.

**Separation of duties:** The administrator manages HSM users but does not own application keys. The crypto user creates, owns and uses keys. HSM users are separate from IAM identities.

### Step 15 - Configure the single-HSM lab exception

Client SDK 5 rejected the key operation:

```text
Cannot perform the requested key operation as the key must be available on at least 2 HSMs.
Either increase the number of HSMs in the cluster, or disable the key availability check.
```

This is a durability safeguard: a persistent key should be replicated to at least two HSMs before use. Because this was a short, cost-controlled lab with one HSM, disable the check for CloudHSM CLI:

```bash
sudo /opt/cloudhsm/bin/configure-cli --disable-key-availability-check
```

**Production position:** Do not disable this check. Deploy multiple HSMs across Availability Zones and retain key-availability quorum. For stronger resilience during replacement events, AWS guidance may justify three HSMs.

### Step 16 - Generate a non-exportable AES-256 key

```text
login --username crypto_user --role crypto-user

key generate-symmetric aes \
  --label cloudhsm_lab_aes \
  --key-length-bytes 32 \
  --attributes encrypt=true decrypt=true extractable=false

key list --filter attr.label=cloudhsm_lab_aes
```

Important attributes:

- `key-type=aes`
- `key-length-bytes=32` (256 bits)
- `local=true` (generated inside the HSM)
- `extractable=false`
- `never-extractable=true`
- `token=true` (persistent rather than session-only)

### Step 17 - Generate a non-exportable RSA key pair

```text
key generate-asymmetric-pair rsa \
  --public-label cloudhsm_lab_rsa_public \
  --private-label cloudhsm_lab_rsa_private \
  --modulus-size-bits 2048 \
  --public-exponent 65537 \
  --public-attributes verify=true \
  --private-attributes sign=true extractable=false
```

The public key was permitted to verify signatures. The private key was permitted to sign and was non-exportable.

### Step 18 - Sign and verify data inside the HSM

The Base64 input `Q2xvdWRIU00gbGFiIHRlc3Q=` represents `CloudHSM lab test`.

```text
crypto sign rsa-pkcs \
  --key-filter attr.label=cloudhsm_lab_rsa_private \
  --hash-function sha256 \
  --data Q2xvdWRIU00gbGFiIHRlc3Q=
```

CloudHSM returned a Base64-encoded signature. Verify it:

```text
crypto verify rsa-pkcs \
  --key-filter attr.label=cloudhsm_lab_rsa_public \
  --hash-function sha256 \
  --data Q2xvdWRIU00gbGFiIHRlc3Q= \
  --signature <SIGNATURE>
```

Result: signature verification succeeded. The private key performed the signing operation inside the HSM and never left it.

As a negative integrity test, verify the same signature against altered data (`CloudHSM lab tampered`):

```text
crypto verify rsa-pkcs \
  --key-filter attr.label=cloudhsm_lab_rsa_public \
  --hash-function sha256 \
  --data Q2xvdWRIU00gbGFiIHRhbXBlcmVk \
  --signature <SAME_SIGNATURE>
```

Expected result: signature verification failed.

## 7. Control plane versus HSM security domain

| Security domain | Identity system | Example operations |
|---|---|---|
| AWS control plane | IAM identities, policies and AWS APIs | Create cluster/HSM, describe cluster, tag, delete HSM |
| HSM data/management plane | HSM-native admin and crypto-user credentials | Create users, generate keys, sign, verify, wrap or share keys |

An AWS administrator with broad IAM permissions does not automatically know HSM user passwords or gain access to HSM keys. Conversely, a crypto user cannot create or delete the AWS CloudHSM cluster unless separately authorized through IAM.

## 8. Production design considerations

### Availability and durability

- Deploy HSMs into multiple Availability Zones.
- Keep key-availability checks enabled.
- Plan for HSM replacement and cluster scaling.
- Test client behavior during HSM loss and replacement.
- Maintain recent cluster backups and test restoration through cloning.

### Identity and access

- Separate AWS infrastructure administrators, HSM administrators and crypto users.
- Use least-privilege IAM roles rather than long-lived IAM user credentials.
- Protect HSM credentials in an approved secrets-management workflow.
- Consider quorum authentication for sensitive user and key-management operations.
- Monitor failed logins; accounts can lock after repeated failures.

### PKI

- Protect a production root CA private key offline or in a separate approved HSM.
- Prefer an intermediate CA for day-to-day issuance so the root remains offline.
- Define certificate policies, revocation, renewal and custody procedures.
- Never copy a root CA private key to general-purpose application hosts.

### Networking

- Use private subnets and tightly scoped security groups.
- Restrict administrative access through Session Manager or controlled bastions.
- Monitor network paths and CloudHSM client logs.
- Ensure time synchronization and DNS/routing dependencies are resilient.

### Monitoring and audit

- Enable and retain CloudHSM audit logs in CloudWatch Logs.
- Monitor AWS CloudTrail for control-plane operations.
- Alert on HSM deletion, cluster changes, failed authentication and unusual key operations.
- Send security logs to the centralized SIEM and protect them against tampering.

## 9. Troubleshooting record

### SSH rejected the private key

**Symptom:** `WARNING: UNPROTECTED PRIVATE KEY FILE` and `bad permissions`.

**Cause:** The Windows ACL allowed identities other than the current user to access the PEM file.

**Resolution:** Remove inherited/broad permissions and grant read access only to the current user.

### RPM download stalled

**Symptom:** `wget` stopped at `Connecting to s3.amazonaws.com:443`.

**Likely cause:** Client outbound networking, route or security configuration.

**Resolution:** Verify internet/NAT path, security groups, NACLs and DNS, then retry.

### PowerShell could not invoke `$OpenSSL`

**Symptom:** The expression after `&` was not a valid command.

**Cause:** `$OpenSSL` was not defined as the executable path in that PowerShell session.

**Resolution:** Set `$OpenSSL = "C:\Program Files\Git\usr\bin\openssl.exe"` before invocation.

### Marvell certificate download returned Access Denied

**Cause:** The vendor CDN blocked the scripted request.

**Resolution:** Use the official Marvell browser landing page and download the certificate manually.

### `hsm-info` was unrecognized

**Cause:** CloudHSM CLI 5.17.2 places the command under the `cluster` group.

**Resolution:** Use `cluster hsm-info`.

### Key generation required two HSMs

**Cause:** Client SDK 5 enables key-availability quorum by default.

**Lab resolution:** `configure-cli --disable-key-availability-check`.

**Production resolution:** Run multiple HSMs and leave the durability check enabled.

## 10. Cleanup checklist

CloudHSM charges accrue per active HSM-hour. After evidence has been captured:

1. Log out and exit CloudHSM CLI.
2. Delete the HSM from the cluster.
3. Wait for HSM deletion to complete.
4. Delete the empty cluster.
5. Terminate the temporary EC2 client.
6. Delete unused lab security groups and temporary networking components.
7. Review CloudHSM backups and remove only those that are no longer required.
8. Verify billing/cost explorer after usage data becomes available.
9. Retain the local documentation and public certificates as appropriate.
10. Protect or securely destroy `customerRootCA.key` according to the chosen retention policy.

Do not delete resources in a broad or automated manner without confirming exact targets and dependencies.

## 11. Technical knowledge checks

### What is AWS CloudHSM?

AWS CloudHSM is a managed service that provides dedicated, single-tenant hardware security modules in an AWS VPC. AWS operates the physical hardware, while the customer controls HSM users, credentials and keys and can integrate applications through standard cryptographic interfaces such as PKCS #11, JCE and OpenSSL.

### When would you choose CloudHSM over KMS?

I would default to KMS for AWS-native encryption because it is simpler and integrates directly with AWS services. I would choose CloudHSM when a regulatory or technical requirement calls for dedicated HSM tenancy, direct control over HSM users, standard interfaces such as PKCS #11, algorithms or operations not available through KMS, or application compatibility with an existing HSM design.

### Describe your hands-on CloudHSM experience

I deployed a FIPS-mode `hsm2m.medium` CloudHSM cluster in `af-south-1` and created an Amazon Linux client in the same VPC. Before initialization, I verified the first HSM through both the AWS CloudHSM and Marvell hardware certificate chains and confirmed that the Cluster CSR public key matched the verified HSM certificate. I created an encrypted customer root CA, signed the CSR, initialized and activated the cluster, created separate admin and crypto-user identities, generated non-exportable AES-256 and RSA keys inside the HSM, and completed RSA-SHA256 signing and verification. I also diagnosed Client SDK 5's key-availability quorum in the single-HSM lab.

### What is the difference between initialization and activation?

Initialization establishes customer ownership by uploading the customer-signed HSM certificate and the issuing CA certificate. Activation occurs through CloudHSM CLI and sets the first administrator password, converting the temporary `unactivated-admin` into a permanent admin and moving the cluster to `ACTIVE`.

### Why verify the hardware certificates?

It gives assurance that the CSR was generated by genuine manufacturer hardware operating within AWS CloudHSM. The HSM certificate is verified through independent AWS and manufacturer chains, and its public key is compared with the CSR public key. This optional process must occur before initialization.

### Why was the Root CA private key not uploaded?

The private key is the customer's trust root and signing authority. AWS needs only the signed cluster certificate and public issuing certificate to validate ownership. Uploading the private key would destroy the custody boundary and allow unauthorized certificate issuance.

### How do IAM and HSM users differ?

IAM controls AWS service-level actions such as creating, describing and deleting clusters or HSMs. CloudHSM uses separate native users inside the HSM. Admins manage HSM users, while crypto users own and use cryptographic keys. IAM access does not automatically provide access to HSM keys.

### What did the key-availability error mean?

Client SDK 5 prevents use of a persistent key until it exists on at least two HSMs. This protects against losing a key that exists on only one appliance. I disabled the check only for a short single-HSM learning environment. In production I would use multiple HSMs across Availability Zones and keep the check enabled.

### How would you harden the lab for production?

I would deploy multiple HSMs across Availability Zones, place clients in private subnets, use tightly scoped security groups and controlled administrative access, keep the key-availability check enabled, separate IAM and HSM duties, use quorum controls for sensitive operations, protect the CA root offline, centralize CloudTrail and HSM audit logs, alert on changes and failed authentication, and regularly test backup restoration and failure scenarios.

### Can AWS see the customer's keys?

AWS manages the hardware service but does not know the customer-defined HSM user credentials and cannot perform customer cryptographic operations. The customer is responsible for users, keys, credentials, availability architecture and recovery planning.

### What happens if all HSMs are deleted?

Live HSM capacity and direct key access are lost. Recovery depends on retained CloudHSM cluster backups and the ability to restore or clone appropriately. This is why multiple HSMs, backups, tested recovery procedures and careful deletion controls are essential.

## 12. Rapid revision sheet

### Five facts to remember

1. CloudHSM is dedicated and customer-controlled; KMS is the simpler managed default.
2. IAM manages the AWS infrastructure; HSM-native users manage users and keys inside the HSM.
3. AWS/Marvell chains verify hardware authenticity; the customer CA establishes ownership.
4. Initialization uploads certificates; activation sets the first HSM admin password.
5. Production requires multiple HSMs and key durability; the single-HSM exception was lab-only.

### Thirty-second answer

> I completed a hands-on AWS CloudHSM deployment in FIPS mode. I built an EC2 client, verified the HSM's AWS and Marvell certificate chains, created a customer CA and used it to initialize the cluster, activated the HSM and separated admin from crypto-user responsibilities. I then generated non-exportable AES and RSA keys inside the HSM and performed an RSA-SHA256 signing and verification test. For cost control the lab used one HSM, so I explicitly disabled Client SDK 5's availability check; in production I would deploy multiple HSMs across AZs and keep that safeguard enabled.

### Do not overstate

Accurate wording:

- â€œI completed a hands-on CloudHSM lab and understand the production architecture.â€
- â€œI deployed and operated a FIPS-mode cluster and performed HSM-backed key operations.â€
- â€œI understand that production requires multi-AZ HSMs, monitoring, backups and formal key custody.â€

Avoid claiming production-scale operational ownership unless you have performed it in a production environment.

## 13. Official references

- [AWS CloudHSM User Guide](https://docs.aws.amazon.com/cloudhsm/latest/userguide/)
- [Verify HSM identity and authenticity](https://docs.aws.amazon.com/cloudhsm/latest/userguide/verify-hsm-identity.html)
- [Initialize a CloudHSM cluster](https://docs.aws.amazon.com/cloudhsm/latest/userguide/initialize-cluster.html)
- [Activate a CloudHSM cluster](https://docs.aws.amazon.com/cloudhsm/latest/userguide/activate-cluster.html)
- [CloudHSM user types](https://docs.aws.amazon.com/cloudhsm/latest/userguide/understanding-users.html)
- [Client SDK 5 key durability settings](https://docs.aws.amazon.com/cloudhsm/latest/userguide/working-client-sync.html)
- [CloudHSM CLI command reference](https://docs.aws.amazon.com/cloudhsm/latest/userguide/cloudhsm_cli-reference.html)

---

**Security note:** This guide deliberately omits all passwords, private-key contents and signature values. Treat the local CA private key and HSM credentials as sensitive material.

