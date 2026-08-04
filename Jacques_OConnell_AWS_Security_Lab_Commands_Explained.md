# AWS Security Lab Commands Explained

## A console user's guide to PowerShell, AWS CLI, OpenSSL, Linux, CloudHSM CLI, Python, and Git

**Prepared for:** Jacques O'Connell  
**Purpose:** Understand the commands used during the AWS CloudHSM, KMS BYOK, IAM hardening, Python auditor, Control Tower, and GitHub labs  
**Prepared:** August 2026

---

## How to use this guide

You do not need to memorise every command. Learn to identify:

1. Which program receives the command.
2. Which AWS service or local file it affects.
3. Whether it only reads information or changes something.
4. How to verify the result.
5. What the equivalent console action would be.

Each command is marked with one of these safety levels:

- **READ:** Retrieves information and normally changes nothing.
- **LOCAL:** Changes files or settings only on your current computer or EC2 instance.
- **AWS CHANGE:** Changes an AWS resource or permission.
- **DESTRUCTIVE:** Deletes, disables, replaces, or makes data unavailable.
- **SECRET:** Handles credentials, private keys, plaintext key material, or passwords.

All identifiers in this guide are placeholders. Do not paste account IDs, keys, tokens, passwords, certificate private keys, or live ARNs into a public repository.

---

# Interview positioning: how the labs were implemented

## Accurate summary

> I used a combination of the AWS console and command-line tooling. The initial provisioning steps that are naturally visual—such as creating the CloudHSM cluster, downloading attestation material, creating the external-origin KMS key, and enabling the Control Tower landing zone—were completed in the AWS console. Most of the detailed implementation and validation was command-line driven using AWS CLI, PowerShell, OpenSSL, Linux tools, CloudHSM CLI, Python/Boto3, and Git. This included IAM and KMS discovery, role assumption with MFA, certificate-chain validation, CSR signing, CloudHSM client configuration, HSM user and key operations, KMS encrypt/decrypt and reimport, CloudTrail evidence queries, posture auditing, tests, and publishing the sanitized documentation to GitHub.

This wording is stronger than saying “I did everything through CLI,” because it is accurate and demonstrates that you can choose the appropriate interface.

## Lab-by-lab evidence

### AWS CloudHSM

- **Console:** Created the cluster and HSM, downloaded the CSR/certificates, uploaded the signed cluster certificate and customer CA certificate, monitored state, and deleted lab resources.
- **Command line:** Connected with SSH, installed/configured the client on Linux, created the customer CA with OpenSSL, validated AWS and Marvell certificate chains, proved CSR/HSM public-key equality, signed the CSR, activated the cluster, created HSM users and keys, and performed RSA signing/verification.
- **Fair description:** Mostly command-line implementation after initial infrastructure provisioning.

### AWS KMS BYOK

- **Console:** Created the external-origin KMS key and downloaded the wrapping public key/import token; some initial material lifecycle actions were performed visually.
- **Command line:** Generated AES material with OpenSSL, wrapped it with RSA-OAEP SHA-256, encrypted/decrypted test data with AWS CLI, decoded binary results in PowerShell, performed explicit existing-material reimport, and queried CloudTrail evidence.
- **Fair description:** Mixed console and CLI, with the cryptographic workflow and validation mainly command-line driven.

### IAM hardening and least privilege

- **Console:** Registered MFA and reviewed identity settings where convenient.
- **Command line:** Inspected policies and keys, assumed the MFA-protected administrator role with STS, activated temporary credentials, tested allowed and denied KMS actions, rotated access credentials, and confirmed the final caller identity.
- **Fair description:** Mostly command-line validation and remediation, with MFA enrollment in the console.

### Python AWS Security Posture Auditor

- **Console:** Minimal; used only for occasional visual confirmation.
- **Command line/code:** Built and executed the Boto3 auditor, created a Python virtual environment, installed dependencies, ran mocked tests, assumed a read-only audit role, generated reports, and validated remediation.
- **Fair description:** Command-line and code driven.

### AWS Control Tower

- **Console:** Enabled the landing zone, created/selected OUs and shared accounts, configured service integrations, reviewed controls, configured Identity Center, and monitored deployment.
- **Command line:** Limited to supplementary validation and the surrounding AWS identity/security work.
- **Fair description:** Console-driven configuration, which is normal for a first hands-on Control Tower deployment.

### GitHub portfolio

- **Command line:** Reviewed repository state, staged and committed sanitized files, pushed feature branches, and handled repository safety configuration.
- **GitHub interface:** Opened, compared, reviewed, and merged pull requests.
- **Fair description:** Git command-line workflow plus GitHub pull-request governance.

## If asked why you used CLI

> I am comfortable in the console, but I used the command line for the detailed work because it makes the exact API operation and parameters visible, gives repeatable evidence, supports automation, and is easier to document and troubleshoot. I still used the console where it added value, especially for unfamiliar multi-step service setup and visual state monitoring. In production I would convert stable repeated workflows into reviewed scripts or infrastructure as code rather than rely on an undocumented sequence of manual commands.

## If asked whether the commands were scripted

> Some commands were run interactively while I learned and verified the workflow. I then documented the commands and converted the posture checks into a tested Python/Boto3 tool. My next maturity step would be to parameterize repeatable provisioning and validation, add safe error handling and idempotency, and run it through a controlled CI/CD or automation workflow using temporary credentials.

---

# 1. The five command environments

## 1.1 PowerShell

PowerShell is the Windows shell in which most of the workstation commands were executed. It interprets variables such as `$OpenSSL`, pipelines using `|`, and commands such as `Get-Item` and `ConvertFrom-Json`.

The prompt:

```text
PS C:\Users\Jacques O'Connell>
```

is not part of the command. Do not copy it.

## 1.2 AWS CLI

AWS CLI sends authenticated API requests to AWS. Its general structure is:

```text
aws <service> <operation> <parameters>
```

Example:

```powershell
aws kms describe-key --key-id alias/example --region af-south-1
```

- `aws` starts AWS CLI.
- `kms` selects AWS Key Management Service.
- `describe-key` is the API operation.
- `--key-id` identifies the key.
- `--region` selects the AWS Region.

The console and CLI generally call the same AWS APIs. The CLI is simply a repeatable way to make the request.

## 1.3 OpenSSL

OpenSSL is a local cryptographic toolkit. In these labs it generated keys, created and inspected certificates, verified trust chains, produced random bytes, and wrapped BYOK material.

OpenSSL does not automatically send anything to AWS. It works on local files unless another command uploads the result.

## 1.4 Linux shell on EC2

After SSH connected to EC2, commands such as `wget`, `sudo`, `yum`, `cp`, and `chmod` were interpreted by the Linux shell on the EC2 instance—not by Windows PowerShell.

The prompt:

```text
[ec2-user@ip-172-31-x-x ~]$
```

is not part of the command.

## 1.5 CloudHSM CLI

CloudHSM CLI operates inside the HSM security domain. Commands such as `user create`, `key generate-symmetric`, and `crypto sign` are not AWS CLI commands.

The prompt:

```text
aws-cloudhsm >
```

shows that you are inside CloudHSM CLI interactive mode. Do not prefix these commands with `aws`.

---

# 2. PowerShell fundamentals used in the labs

## 2.1 The backtick: continue a command on the next line

```powershell
aws kms describe-key `
    --region af-south-1 `
    --key-id alias/example
```

**Safety:** READ

The PowerShell backtick tells PowerShell that the command continues on the following line. It improves readability but does not change the request.

Important rules:

- The backtick must be the final character on the line.
- A space after it can break continuation.
- Bash uses a backslash (`\`) instead. A Bash backslash caused the earlier `unrecognized arguments: \` error when used in PowerShell.
- A one-line version is often safer when learning.

Equivalent one-line command:

```powershell
aws kms describe-key --region af-south-1 --key-id alias/example
```

## 2.2 Variables

```powershell
$OpenSSL = "C:\Program Files\Git\usr\bin\openssl.exe"
```

**Safety:** LOCAL

This creates a PowerShell variable named `OpenSSL` containing a path. It does not run OpenSSL and does not change the file.

Use the variable later:

```powershell
& $OpenSSL version
```

The `&` is PowerShell's call operator. It executes the path stored in the variable. This was necessary because the path contains spaces.

## 2.3 Pipelines

```powershell
aws kms describe-key --key-id alias/example --output json |
    ConvertFrom-Json
```

**Safety:** READ

The pipe sends the text output from the left command into the command on the right. `ConvertFrom-Json` converts JSON text into a PowerShell object whose fields can be accessed as properties.

Example:

```powershell
$Result = aws kms describe-key --key-id alias/example --output json |
    ConvertFrom-Json

$Result.KeyMetadata.KeyState
```

The first command stores the object; the second reads its `KeyState` property.

## 2.4 Environment variables

```powershell
$env:PYTHONPATH = "$PWD\src"
```

**Safety:** LOCAL

- `$env:` selects an environment variable.
- `PYTHONPATH` tells Python where to look for modules.
- `$PWD` is the current directory.
- This change affects the current PowerShell process and child processes. It is not an AWS change.

Temporary AWS credentials were also loaded into environment variables:

```powershell
$env:AWS_ACCESS_KEY_ID     = $Session.Credentials.AccessKeyId
$env:AWS_SECRET_ACCESS_KEY = $Session.Credentials.SecretAccessKey
$env:AWS_SESSION_TOKEN     = $Session.Credentials.SessionToken
```

**Safety:** SECRET

These variables make subsequent AWS CLI calls use the temporary role session. Never print, screenshot, commit, or permanently store their values. Close the shell or remove the variables after use.

## 2.5 Select properties for readable output

```powershell
Get-Item ".\PlaintextKeyMaterial.bin" |
    Select-Object Name, Length
```

**Safety:** READ

`Get-Item` retrieves local file metadata. `Select-Object` displays only the name and size. This verified that the BYOK material was exactly 32 bytes without displaying its secret contents.

## 2.6 Write binary data correctly

```powershell
[IO.File]::WriteAllBytes(
    (Join-Path $PWD "byok-ciphertext.bin"),
    [Convert]::FromBase64String([string]$EncryptResult.CiphertextBlob)
)
```

**Safety:** LOCAL

AWS CLI returned the ciphertext as Base64 text inside JSON. This command:

1. Reads the `CiphertextBlob` field.
2. Converts Base64 text back into binary bytes.
3. Builds a safe path in the current folder.
4. Writes the binary file.

This solved the earlier error where `kms-ciphertext.bin` did not exist. A normal text-writing command should not be used for arbitrary binary data.

## 2.7 Decode Base64 plaintext

```powershell
[Text.Encoding]::ASCII.GetString(
    [Convert]::FromBase64String([string]$DecryptResult.Plaintext)
)
```

**Safety:** SECRET

KMS returned decrypted plaintext as Base64. The command converted it to bytes and decoded the bytes as ASCII text. In a production script, avoid displaying sensitive plaintext in logs or terminal history.

## 2.8 Loops

```powershell
$Events = @(
    "GetParametersForImport",
    "ImportKeyMaterial",
    "DeleteImportedKeyMaterial",
    "Encrypt",
    "Decrypt"
)

foreach ($EventName in $Events) {
    aws cloudtrail lookup-events `
        --region af-south-1 `
        --lookup-attributes AttributeKey=EventName,AttributeValue=$EventName `
        --max-results 10 `
        --output table
}
```

**Safety:** READ

`@(...)` creates a list. `foreach` executes the CloudTrail lookup once for each event name. This replaces five manually repeated commands with one reusable block.

## 2.9 Why copied table output caused PowerShell errors

Text such as this is output, not a command:

```text
|+----------------------------------------+-----------------+|
|| PolicyArn                              | PolicyName      ||
```

When pasted at a PowerShell prompt, `|` is interpreted as a pipeline operator, so PowerShell reported empty-pipeline and parsing errors. Only copy text from a fenced command block, not the table displayed after it.

---

# 3. AWS CLI discovery and identity commands

## 3.1 Confirm the current identity

```powershell
aws sts get-caller-identity
```

**Safety:** READ

This calls AWS Security Token Service and returns:

- `UserId`: internal principal/session identifier.
- `Account`: 12-digit AWS account ID.
- `Arn`: the current IAM user or assumed-role session ARN.

Use it before any sensitive command and after assuming a role. It answers: “Who will AWS treat me as?”

**Console equivalent:** Open the account menu and inspect the account/role, although `get-caller-identity` is more precise for CLI credentials.

## 3.2 Show only the ARN

```powershell
aws sts get-caller-identity --query Arn --output text
```

**Safety:** READ

- `--query Arn` uses JMESPath to select one field.
- `--output text` returns plain text rather than JSON.

This was used to prove whether the shell was still the IAM user or an assumed role.

## 3.3 List configured profiles

```powershell
aws configure list-profiles
```

**Safety:** READ / LOCAL

This reads local AWS CLI configuration files and lists named profiles. It does not query AWS. When only `default` appeared, the requested `devops-user-rotated` profile did not exist.

## 3.4 Show credential sources

```powershell
aws configure list
```

**Safety:** READ / LOCAL

This shows where the CLI obtained its profile, masked access key, Region, and other settings. It helped identify that credentials came from the shared credentials file while the Region came from an environment variable.

It masks secrets, but screenshots can still reveal profile names and partial key IDs.

## 3.5 List resources and format results

```powershell
aws kms list-keys `
    --region af-south-1 `
    --query "Keys[].{KeyId:KeyId,KeyArn:KeyArn}" `
    --output table
```

**Safety:** READ

- `list-keys` returns KMS keys in the Region.
- `Keys[]` means every item in the `Keys` array.
- `{KeyId:KeyId,KeyArn:KeyArn}` builds a smaller object for each key.
- `table` is human-readable.

**Console equivalent:** KMS → Customer managed keys and AWS managed keys.

## 3.6 Inspect a KMS key

```powershell
aws kms describe-key `
    --region af-south-1 `
    --key-id <key-id> `
    --query "KeyMetadata.{KeyId:KeyId,Description:Description,Manager:KeyManager,Origin:Origin,State:KeyState,Usage:KeyUsage}" `
    --output table
```

**Safety:** READ

This retrieves KMS key metadata, not the cryptographic material. KMS never returns plaintext key material through `DescribeKey`.

## 3.7 List KMS aliases

```powershell
aws kms list-aliases `
    --region af-south-1 `
    --query "Aliases[].{Alias:AliasName,TargetKeyId:TargetKeyId}" `
    --output table
```

**Safety:** READ

Aliases are friendly pointers such as `alias/aws/s3` or `alias/personal-byok-lab`. An alias can exist without a target key in some service-managed situations.

---

# 4. IAM and STS commands

## 4.1 Inspect attached user policies

```powershell
aws iam list-attached-user-policies `
    --user-name <iam-user> `
    --output table
```

**Safety:** READ

This lists managed policies attached directly to an IAM user. It revealed `AdministratorAccess` attached to the user.

**Console equivalent:** IAM → Users → user → Permissions.

## 4.2 Inspect inline user policies

```powershell
aws iam list-user-policies `
    --user-name <iam-user> `
    --output table
```

**Safety:** READ

This lists policy names embedded directly in the user. It does not list AWS-managed or customer-managed attached policies.

## 4.3 List access keys

```powershell
aws iam list-access-keys `
    --user-name <iam-user> `
    --query "AccessKeyMetadata[].{KeyId:AccessKeyId,Status:Status,Created:CreateDate}" `
    --output table
```

**Safety:** READ

This shows key IDs, status, and creation dates. It never returns an existing secret access key. AWS displays a secret access key only when the key is created.

The earlier `AccessDenied` was expected after direct administrator access was removed: the base user no longer had `iam:ListAccessKeys`. The operation had to be performed through the administrator role.

## 4.4 Create a role session with MFA

```powershell
$MfaCode = Read-Host "Enter the six-digit MFA code"

$AdminSession = aws sts assume-role `
    --role-arn "arn:aws:iam::<account-id>:role/PersonalAdministratorRole" `
    --role-session-name "AdminValidation" `
    --serial-number "arn:aws:iam::<account-id>:mfa/<iam-user>" `
    --token-code $MfaCode `
    --duration-seconds 3600 `
    --output json | ConvertFrom-Json
```

**Safety:** AWS CHANGE / SECRET

This does not modify the role. It asks STS for temporary credentials:

- `--role-arn`: role to assume.
- `--role-session-name`: audit-friendly name visible in CloudTrail.
- `--serial-number`: MFA device ARN.
- `--token-code`: current six-digit TOTP.
- `--duration-seconds`: requested session length.

The error `--token-code: expected one argument` occurred because `$MfaCode` was empty. `Read-Host` must run before the STS command.

**Console equivalent:** Switch Role or use IAM Identity Center. The explicit CLI command is useful for testing MFA trust conditions.

## 4.5 Activate the temporary session

```powershell
$env:AWS_ACCESS_KEY_ID = $AdminSession.Credentials.AccessKeyId
$env:AWS_SECRET_ACCESS_KEY = $AdminSession.Credentials.SecretAccessKey
$env:AWS_SESSION_TOKEN = $AdminSession.Credentials.SessionToken

aws sts get-caller-identity
```

**Safety:** SECRET

The three environment variables must be used together. The session token distinguishes temporary STS credentials from long-lived access keys. The final command should return an ARN containing `assumed-role/PersonalAdministratorRole/`.

## 4.6 Remove temporary credentials

```powershell
Remove-Item Env:AWS_ACCESS_KEY_ID -ErrorAction SilentlyContinue
Remove-Item Env:AWS_SECRET_ACCESS_KEY -ErrorAction SilentlyContinue
Remove-Item Env:AWS_SESSION_TOKEN -ErrorAction SilentlyContinue
```

**Safety:** LOCAL

This removes temporary credentials from the current PowerShell process. The session may still exist until expiration, but this shell no longer presents it to AWS CLI.

## 4.7 Access-key rotation concept

The safe sequence is:

1. Create a new access key.
2. Configure and test the new key.
3. Inactivate the old key.
4. Test again.
5. Delete the exact old key.

Example destructive command:

```powershell
aws iam delete-access-key `
    --user-name <iam-user> `
    --access-key-id <old-access-key-id>
```

**Safety:** DESTRUCTIVE

There is no recovery for a deleted access key. Verify the exact ID and confirm the replacement works first.

---

# 5. KMS policy and lifecycle commands

## 5.1 Read a key policy

```powershell
$Policy = aws kms get-key-policy `
    --region af-south-1 `
    --key-id <key-id-or-key-arn> `
    --policy-name default `
    --query Policy `
    --output text | ConvertFrom-Json

$Policy | ConvertTo-Json -Depth 20
```

**Safety:** READ

`GetKeyPolicy` did not accept the alias in this lab, producing `InvalidArnException`. Using the key ID or ARN worked.

The API returned the policy as a JSON string. The first `ConvertFrom-Json` turned it into an object; the second `ConvertTo-Json -Depth 20` printed the nested object clearly.

**Console equivalent:** KMS → key → Key policy.

## 5.2 Enable automatic rotation

```powershell
aws kms enable-key-rotation `
    --region af-south-1 `
    --key-id <customer-managed-key-id>
```

**Safety:** AWS CHANGE

This enables automatic rotation for an eligible customer-managed key. It does not immediately re-encrypt existing data.

Verify:

```powershell
aws kms get-key-rotation-status `
    --region af-south-1 `
    --key-id <key-id> `
    --output table
```

**Safety:** READ

## 5.3 Test least privilege

```powershell
aws kms describe-key `
    --region af-south-1 `
    --key-id <key-id>
```

should succeed for the test role, while:

```powershell
aws kms disable-key `
    --region af-south-1 `
    --key-id <key-id>
```

should fail with `AccessDeniedException` when the role lacks `kms:DisableKey`.

**Safety:** First command READ; second command DESTRUCTIVE if authorized.

The denied command was a successful security test: it proved the role could use or inspect the key but could not administer its lifecycle.

---

# 6. BYOK and OpenSSL commands

## 6.1 Generate 256-bit key material

```powershell
$OpenSSL = "C:\Program Files\Git\usr\bin\openssl.exe"
& $OpenSSL rand -out PlaintextKeyMaterial.bin 32
```

**Safety:** LOCAL / SECRET

- `rand` generates cryptographically secure random bytes.
- `-out` writes them to a file.
- `32` bytes equals 256 bits.

This file was the actual external AES key material. It must never be committed, emailed, logged, or uploaded unwrapped.

**Console equivalent:** None. The console cannot generate customer-held external key material for you; that would defeat the customer-origin requirement.

## 6.2 Wrap the material

```powershell
& $OpenSSL pkeyutl `
    -encrypt `
    -in PlaintextKeyMaterial.bin `
    -out EncryptedKeyMaterial.bin `
    -inkey WrappingPublicKey.bin `
    -keyform DER `
    -pubin `
    -pkeyopt rsa_padding_mode:oaep `
    -pkeyopt rsa_oaep_md:sha256 `
    -pkeyopt rsa_mgf1_md:sha256
```

**Safety:** LOCAL / SECRET

Breakdown:

- `pkeyutl`: public-key operation tool.
- `-encrypt`: encrypt rather than decrypt or sign.
- `-in`: plaintext external key material.
- `-out`: wrapped transport file.
- `-inkey`: temporary public wrapping key downloaded from KMS.
- `-keyform DER`: the wrapping key is binary DER, not PEM text.
- `-pubin`: input is a public key.
- OAEP/SHA-256 options must match the selection used when requesting the KMS import parameters.

The KMS import token and wrapping public key are a matched, temporary set. Do not mix sets from different downloads.

## 6.3 Create test plaintext

```powershell
Set-Content `
    -Path ".\byok-plaintext.txt" `
    -Value "AWS KMS BYOK lab test" `
    -Encoding ascii `
    -NoNewline
```

**Safety:** LOCAL

This creates a small local test file. `-NoNewline` avoids adding an extra line-ending byte.

## 6.4 Encrypt with KMS

```powershell
$EncryptResult = aws kms encrypt `
    --region af-south-1 `
    --key-id alias/personal-byok-lab `
    --plaintext fileb://byok-plaintext.txt `
    --encryption-context Purpose=BYOKLab `
    --output json | ConvertFrom-Json
```

**Safety:** AWS CHANGE / SECRET

- `fileb://` tells AWS CLI to read raw binary bytes from a file.
- `--encryption-context` supplies non-secret authenticated data.
- The command returns Base64 ciphertext in JSON; it does not automatically create `byok-ciphertext.bin`.

**Console equivalent:** The KMS console manages keys but does not provide a general-purpose Encrypt/Decrypt textbox. These operations are normally performed through an application, SDK, or CLI.

## 6.5 Decrypt with the same context

```powershell
$DecryptResult = aws kms decrypt `
    --region af-south-1 `
    --ciphertext-blob fileb://byok-ciphertext.bin `
    --encryption-context Purpose=BYOKLab `
    --output json | ConvertFrom-Json
```

**Safety:** SECRET

The same context must be supplied. A different value causes `InvalidCiphertextException`. Encryption context is authenticated but not secret and can appear in CloudTrail.

## 6.6 Reimport existing material

```powershell
$ByokKeyId = aws kms describe-key `
    --region af-south-1 `
    --key-id alias/personal-byok-lab `
    --query KeyMetadata.KeyId `
    --output text

aws kms import-key-material `
    --region af-south-1 `
    --key-id $ByokKeyId `
    --encrypted-key-material fileb://reimport-parameters/ReimportEncryptedKeyMaterial.bin `
    --import-token fileb://reimport-parameters/ImportToken.bin `
    --expiration-model KEY_MATERIAL_DOES_NOT_EXPIRE `
    --import-type EXISTING_KEY_MATERIAL
```

**Safety:** AWS CHANGE / SECRET

The first command resolves the alias to a key ID because import operations require the logical key identity. The second uploads the wrapped material and matched token.

`EXISTING_KEY_MATERIAL` means the exact material was previously associated with this logical KMS key. Using `NEW_KEY_MATERIAL` caused `IncorrectKeyMaterialException`.

## 6.7 Delete imported material

```powershell
aws kms delete-imported-key-material `
    --region af-south-1 `
    --key-id <key-id>
```

**Safety:** DESTRUCTIVE

This makes the KMS key unusable and normally returns it to `PendingImport`. Existing ciphertext remains but cannot be decrypted until identical material is reimported into the same logical KMS key.

Do not run this against production without verified custody, impact analysis, approval, and a tested recovery procedure.

---

# 7. SSH, SCP, and Linux commands

## 7.1 Connect to EC2

```powershell
ssh -i "C:\Users\<username>\Downloads\<key-pair>.pem" `
    ec2-user@<ec2-public-dns>
```

**Safety:** READ / REMOTE SESSION

- `ssh` creates an encrypted remote shell.
- `-i` identifies the private key file.
- `ec2-user` is the Amazon Linux login user.
- The DNS name identifies the EC2 host.

**Console equivalent:** EC2 Instance Connect or Systems Manager Session Manager, if configured.

The “UNPROTECTED PRIVATE KEY FILE” error meant other Windows identities had read permission to the PEM file. SSH ignored it to protect the private key. Restricting the file ACL solved the problem.

## 7.2 Copy a file to EC2

```powershell
scp -i "C:\Users\<username>\Downloads\<key-pair>.pem" `
    ".\customerRootCA.crt" `
    ec2-user@<ec2-public-dns>:/home/ec2-user/
```

**Safety:** REMOTE CHANGE

`scp` securely copies a file over SSH. Only the public CA certificate was copied. The private key `customerRootCA.key` remained on the workstation.

## 7.3 Download the CloudHSM package

```bash
wget https://s3.amazonaws.com/cloudhsmv2-software/CloudHsmClient/Amzn2023/cloudhsm-cli-latest.amzn2023.x86_64.rpm
```

**Safety:** LOCAL ON EC2

`wget` downloads the RPM package into the current EC2 directory. If it stalls at “Connecting,” investigate routing, Internet/NAT access, DNS, security groups, NACLs, and proxy configuration.

## 7.4 Install the RPM

```bash
sudo yum install -y ./cloudhsm-cli-latest.amzn2023.x86_64.rpm
```

**Safety:** LOCAL ON EC2 / CHANGE

- `sudo` runs with root privileges.
- `yum install` installs software and dependencies.
- `-y` automatically confirms prompts.
- `./` means the RPM in the current directory.

## 7.5 Copy and permission the CA certificate

```bash
sudo cp /home/ec2-user/customerRootCA.crt /opt/cloudhsm/etc/customerRootCA.crt
sudo chmod 644 /opt/cloudhsm/etc/customerRootCA.crt
```

**Safety:** LOCAL ON EC2 / CHANGE

- `cp` copies the certificate into the CloudHSM configuration directory.
- `chmod 644` means owner can read/write; group and others can read.
- This is appropriate for a public certificate, not a private key.

## 7.6 Configure the CloudHSM client

```bash
sudo /opt/cloudhsm/bin/configure-cli -a <hsm-private-ip>
sudo /opt/cloudhsm/bin/configure-cli \
  --hsm-ca-cert /opt/cloudhsm/etc/customerRootCA.crt
```

**Safety:** LOCAL ON EC2 / CHANGE

The first command tells the client which private HSM IP to use. The second identifies the customer CA certificate used to validate the cluster certificate.

The Bash backslash continues the command. It is different from the PowerShell backtick.

## 7.7 Inspect a configuration file

```bash
cat /opt/cloudhsm/etc/cloudhsm-cli.cfg
```

**Safety:** READ

`cat` displays the file. Review configuration output before sharing; configuration files can contain internal addresses or other sensitive environment details.

---

# 8. OpenSSL certificate commands from CloudHSM

## 8.1 Create an encrypted RSA CA private key

```powershell
& $OpenSSL genrsa -aes256 -out customerRootCA.key 3072
```

**Safety:** LOCAL / SECRET

- `genrsa`: generate an RSA private key.
- `-aes256`: encrypt the key file with a passphrase.
- `3072`: RSA modulus size.

The passphrase protects the file at rest. It should be long, unique, securely stored, and never committed. Losing the passphrase makes the encrypted key unusable.

## 8.2 Create a self-signed root CA certificate

```powershell
& $OpenSSL req -new -x509 -sha256 -days 3650 `
    -key customerRootCA.key `
    -out customerRootCA.crt `
    -addext "basicConstraints=critical,CA:TRUE" `
    -addext "keyUsage=critical,keyCertSign,cRLSign"
```

**Safety:** LOCAL / SECRET KEY USE

- `req`: certificate request/certificate tool.
- `-new -x509`: create a new self-signed certificate instead of only a CSR.
- `-sha256`: signature digest.
- `-days 3650`: ten-year lab validity.
- `CA:TRUE`: certificate may act as a CA.
- `keyCertSign,cRLSign`: key may sign certificates and revocation lists.

The `.key` is secret; the `.crt` is public.

## 8.3 Inspect a certificate

```powershell
& $OpenSSL x509 `
    -in customerRootCA.crt `
    -noout -subject -issuer -dates
```

**Safety:** READ

- `x509`: operate on an X.509 certificate.
- `-noout`: do not print the full encoded certificate.
- `-subject`, `-issuer`, `-dates`: print selected fields.

When subject equals issuer, the root certificate is self-signed.

## 8.4 Verify a certificate chain

```powershell
& $OpenSSL verify `
    -CAfile "<cluster-id>_AWS_chain.crt" `
    "<cluster-id>_HsmCertificate.crt"
```

**Safety:** READ

OpenSSL attempts to build a trust path from the HSM certificate to a root in `-CAfile`. `OK` means signatures and chain construction validated for the requested purpose; it does not prove every operational or policy requirement.

## 8.5 Extract and compare public keys

```powershell
& $OpenSSL x509 -in "<cluster-id>_HsmCertificate.crt" -pubkey -noout |
    Set-Content "HsmCertificate.pub" -Encoding ascii

& $OpenSSL req -in "<cluster-id>_ClusterCsr.csr" -pubkey -noout |
    Set-Content "ClusterCsr.pub" -Encoding ascii

Get-FileHash "HsmCertificate.pub", "ClusterCsr.pub" -Algorithm SHA256
```

**Safety:** READ / LOCAL FILES

This extracted the public key from the verified HSM certificate and from the unsigned CSR, then hashed both files. Matching hashes proved the CSR contained the same public key as the verified HSM identity.

This did not compare private keys; private HSM key material was never exported.

## 8.6 Sign the cluster CSR

```powershell
& $OpenSSL x509 -req -sha256 -days 3650 `
    -in "<cluster-id>_ClusterCsr.csr" `
    -CA "customerRootCA.crt" `
    -CAkey "customerRootCA.key" `
    -CAcreateserial `
    -out "<cluster-id>_CustomerHsmCertificate.crt"
```

**Safety:** LOCAL / SECRET KEY USE

This used the customer CA private key to sign the cluster CSR. The output certificate established customer ownership during CloudHSM initialization. Only the signed certificate and public CA certificate were uploaded—not the private key.

---

# 9. CloudHSM CLI commands

## 9.1 Enter interactive mode

```bash
/opt/cloudhsm/bin/cloudhsm-cli interactive
```

**Safety:** LOCAL CLIENT SESSION

This starts the separate CloudHSM command environment. It does not log you into an HSM user automatically.

## 9.2 Inspect cluster HSMs

```text
cluster hsm-info
```

**Safety:** READ

The earlier `hsm-info` failed because Client SDK 5 expects the `cluster` command group. Command syntax can change between tool versions; use `--help` rather than guessing.

## 9.3 List HSM users

```text
user list
```

**Safety:** READ

This lists HSM-native users. These are not IAM users and do not appear in the IAM console.

## 9.4 Activate the cluster

```text
cluster activate
```

**Safety:** AWS/HSM CHANGE / SECRET

This changes the first unactivated administrator into a permanent HSM administrator and sets the initial password. It is a one-time ownership step after cluster initialization.

## 9.5 Log in and create a crypto user

```text
login --username admin --role admin
user create --username crypto_user --role crypto-user
```

**Safety:** HSM CHANGE / SECRET

The administrator manages users. The crypto user creates and uses application keys. Passwords were entered interactively so they did not appear in command history.

## 9.6 Generate an AES key

```text
key generate-symmetric aes \
  --label cloudhsm_lab_aes \
  --key-length-bytes 32 \
  --attributes encrypt=true decrypt=true extractable=false
```

**Safety:** HSM CHANGE / SECRET KEY

- AES with 32 bytes creates a 256-bit symmetric key.
- `encrypt=true decrypt=true` permits those operations.
- `extractable=false` prevents plaintext key export.
- The key is generated inside the HSM.

## 9.7 Generate an RSA key pair

```text
key generate-asymmetric-pair rsa \
  --public-label cloudhsm_lab_rsa_public \
  --private-label cloudhsm_lab_rsa_private \
  --modulus-size-bits 2048 \
  --public-exponent 65537 \
  --public-attributes verify=true \
  --private-attributes sign=true extractable=false
```

**Safety:** HSM CHANGE / SECRET KEY

The public key may verify signatures. The private key may sign and is non-exportable.

## 9.8 Sign and verify

```text
crypto sign rsa-pkcs \
  --key-filter attr.label=cloudhsm_lab_rsa_private \
  --hash-function sha256 \
  --data <base64-data>
```

```text
crypto verify rsa-pkcs \
  --key-filter attr.label=cloudhsm_lab_rsa_public \
  --hash-function sha256 \
  --data <same-base64-data> \
  --signature <base64-signature>
```

**Safety:** CRYPTOGRAPHIC OPERATION

The first command asks the HSM private key to sign a SHA-256 digest using RSA PKCS#1 v1.5. The private key remains inside the HSM. The second uses the public key to verify integrity and authenticity.

## 9.9 Single-HSM lab exception

```bash
sudo /opt/cloudhsm/bin/configure-cli --disable-key-availability-check
```

**Safety:** LOCAL CONFIGURATION / HIGH RISK

This disabled a client safeguard requiring a key to be available on at least two HSMs. It was used only because the short lab had one HSM for cost control.

Do not present this as a production setting. Production should use multiple HSMs across Availability Zones and keep the availability check enabled.

---

# 10. Python security auditor commands

## 10.1 Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Safety:** LOCAL

The first command creates an isolated Python environment in `.venv`. The second changes the current shell so `python` and `pip` use that environment.

The `(.venv)` prefix in the prompt confirms activation. It is not part of the command.

## 10.2 Install dependencies

```powershell
python -m pip install -r requirements.txt
```

**Safety:** LOCAL / SOFTWARE CHANGE

This installs the packages listed in `requirements.txt` into the virtual environment. `python -m pip` helps ensure pip belongs to the selected Python interpreter.

## 10.3 Run tests

```powershell
$env:PYTHONPATH = "$PWD\src"
pytest -q
```

**Safety:** LOCAL

- `PYTHONPATH` exposes the local `src` package.
- `pytest` discovers and runs tests.
- `-q` means quiet output.

Mocked tests validate logic without changing AWS resources.

## 10.4 Run the auditor

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m aws_security_auditor.cli --regions af-south-1
```

**Safety:** READ AGAINST AWS

- `-m` runs the package module as a program.
- `--regions` limits regional checks.
- The tool verifies it is running through the dedicated `SecurityAuditLabRole`.
- It writes console, JSON, and CSV findings locally.

The reports can contain live resource identifiers and should be sanitized before publishing.

---

# 11. Git and GitHub commands

## 11.1 Inspect repository state

```powershell
git status
```

**Safety:** READ / LOCAL

Shows changed, staged, and untracked files. Run it before every commit to prevent uploading secrets or unrelated files.

## 11.2 Stage selected files

```powershell
git add README.md cloudhsm kms-byok python-security-posture-auditor control-tower
```

**Safety:** LOCAL CHANGE

Stages specific paths for the next commit. Prefer explicit paths over `git add .` in security repositories because the latter can stage secrets accidentally.

## 11.3 Review staged changes

```powershell
git diff --cached
```

**Safety:** READ / LOCAL

Shows exactly what the next commit will contain. Search for account IDs, keys, tokens, hostnames, IP addresses, Terraform state, and certificate private keys.

## 11.4 Commit

```powershell
git commit -m "Add AWS security lab documentation"
```

**Safety:** LOCAL CHANGE

Creates a local repository snapshot. It does not upload to GitHub.

## 11.5 Push a branch

```powershell
git push -u origin <branch-name>
```

**Safety:** REMOTE CHANGE

- `origin` is the GitHub remote.
- `-u` records the upstream branch for future pushes.
- This publishes commits and may trigger GitHub Actions.

## 11.6 Safe-directory warning

```powershell
git config --global --add safe.directory "<repository-path>"
```

**Safety:** LOCAL SECURITY CONFIGURATION

Git refused the repository because the directory owner differed from the current Windows user. The exception tells Git to trust that exact path. Add only the exact repository you recognize; do not use a broad wildcard.

---

# 12. Control Tower: mostly console work

The Control Tower lab was intentionally performed in the AWS console. The important lesson is that console actions still call AWS APIs and created resources across multiple services:

- AWS Organizations and organizational units.
- Log Archive and Security Audit accounts.
- IAM Identity Center users, groups, permission sets, and assignments.
- Organization CloudTrail and S3 log buckets.
- AWS Config integration and aggregation.
- Control Tower baselines, controls, roles, StackSets, and Service Catalog resources.

Useful read-only validation commands include:

```powershell
aws organizations describe-organization
aws organizations list-roots
aws organizations list-organizational-units-for-parent --parent-id <root-id>
aws organizations list-accounts --output table
aws cloudtrail describe-trails --include-shadow-trails --output table
aws configservice describe-configuration-aggregators --region af-south-1
```

**Safety:** READ

Do not manually delete Control Tower-managed resources with CLI commands. Use the supported Control Tower decommissioning workflow if the landing zone must be removed, then review retained artifacts separately.

---

# 13. Error messages translated

## `unrecognized arguments: \`

**Meaning:** A Bash line-continuation character was pasted into PowerShell.  
**Fix:** Put the command on one line or use a PowerShell backtick.

## `Table output unavailable`

**Meaning:** The AWS/Azure CLI returned a complex object that could not automatically become a table.  
**Fix:** Use JSON or select simple fields with `--query` before `--output table`.

## `InvalidArnException: Key Aliases are not supported`

**Meaning:** That KMS operation required a key ID or ARN rather than an alias.  
**Fix:** Resolve the alias with `describe-key`, then use the returned key ID/ARN.

## `AccessDeniedException`

**Meaning:** AWS evaluated the caller, action, resource, policies, and conditions and found no effective allow or found an explicit deny.  
**Fix:** Confirm the caller first, then inspect identity policy, resource/key policy, trust policy, SCP, boundary, session policy, endpoint policy, and conditions.

## `No such file or directory`

**Meaning:** The current directory or file name did not match the path passed to the command.  
**Fix:** Run `Get-Location`, `Get-ChildItem`, and `Get-Item` in PowerShell or `pwd` and `ls` in Linux.

## `Value cannot be null` after decryption

**Meaning:** The previous command failed, so the variable expected to contain Base64 plaintext was empty.  
**Fix:** Stop and fix the first error. Do not keep executing dependent commands.

## `IncorrectKeyMaterialException`

**Meaning:** The imported material was already associated with the KMS key but the request treated it as new material.  
**Fix:** Use a fresh wrapping-key/token pair and the correct reimport type, `EXISTING_KEY_MATERIAL`.

## `UNPROTECTED PRIVATE KEY FILE`

**Meaning:** Other Windows identities could read the SSH private key.  
**Fix:** Restrict its ACL to the current user before reconnecting.

## `Cannot perform ... key must be available on at least 2 HSMs`

**Meaning:** CloudHSM Client SDK was protecting key durability.  
**Lab fix:** Disable the check only for the single-HSM disposable lab.  
**Production fix:** Add HSMs across Availability Zones and keep the check enabled.

---

# 14. Console-to-command translation

## “Who am I?”

- **Console:** account/role menu.
- **CLI:** `aws sts get-caller-identity`.

## “Show my KMS keys”

- **Console:** KMS → Customer managed keys.
- **CLI:** `aws kms list-keys` plus `aws kms list-aliases`.

## “Inspect a key”

- **Console:** KMS → key → General configuration.
- **CLI:** `aws kms describe-key`.

## “See the key policy”

- **Console:** KMS → key → Key policy.
- **CLI:** `aws kms get-key-policy`.

## “See IAM user policies”

- **Console:** IAM → Users → user → Permissions.
- **CLI:** `list-attached-user-policies` and `list-user-policies`.

## “Switch to a role”

- **Console:** Switch Role or IAM Identity Center portal.
- **CLI:** `aws sts assume-role`, or configure an AWS CLI role/SSO profile.

## “See CloudTrail operations”

- **Console:** CloudTrail → Event history.
- **CLI:** `aws cloudtrail lookup-events`.

## “Upload imported key material”

- **Console:** KMS → key → Key material → Import.
- **CLI:** `aws kms import-key-material`.

---

# 15. Safe operating workflow

Before running any unfamiliar command:

1. Identify the shell: PowerShell, Bash, AWS CLI, or CloudHSM CLI.
2. Replace placeholders deliberately; never paste angle-bracket placeholders literally.
3. Run the identity check: `aws sts get-caller-identity`.
4. Confirm account, Region, resource ID, current directory, and file names.
5. Classify the command as read, change, destructive, or secret-handling.
6. Use `--help` for the exact tool version.
7. Prefer a read-only `describe`, `get`, or `list` command first.
8. Capture current state and recovery information.
9. Run the smallest scoped command.
10. Verify the result with an independent read command and CloudTrail where appropriate.

For destructive commands, require a second check of the exact resource and a clear recovery/cleanup plan.

---

# 16. Quick-reference cheat sheet

## PowerShell

```powershell
Get-Location                         # current directory
Get-ChildItem                       # list files
Get-Item .\file.bin                 # inspect one file
$Variable = "value"                 # create variable
& $ProgramPath argument             # execute path stored in variable
$CommandOutput | ConvertFrom-Json   # convert JSON text to object
$env:NAME = "value"                # process environment variable
Remove-Item Env:NAME                # remove environment variable
```

## AWS identity

```powershell
aws sts get-caller-identity
aws configure list
aws configure list-profiles
```

## AWS CLI help

```powershell
aws help
aws kms help
aws kms describe-key help
```

## AWS output

```powershell
--output json      # complete structured output
--output table     # readable simple output
--output text      # plain text for variables/scripts
--query "..."      # JMESPath selection/filter
```

## Local file prefixes in AWS CLI

```text
file://path        Load text/encoded parameter content from a file
fileb://path       Load raw binary bytes from a file
```

## Linux orientation

```bash
pwd                # current directory
ls -la             # files including hidden files
cat file           # display text file
cp source target   # copy
chmod 644 file     # change Unix permissions
sudo command       # run command with elevated privileges
```

## Git safety

```powershell
git status
git diff
git diff --cached
git log --oneline -5
```

---

# Appendix A. What to memorise for the interview

Do not memorise command syntax. Be able to explain:

- AWS CLI uses the same service APIs as the console.
- `get-caller-identity` confirms the active security principal.
- `--query` selects fields; `--output` changes presentation.
- STS returns temporary access key, secret key, and session token.
- PowerShell backticks and Bash backslashes are different.
- OpenSSL handled local cryptography; AWS CLI handled AWS APIs.
- CloudHSM CLI used HSM-native users and keys, separate from IAM.
- BYOK plaintext material never went to AWS unwrapped.
- Encryption context must match during decryption.
- An `AccessDenied` is evidence to investigate, not a reason to grant administrator access.
- Every destructive command needs identity, scope, impact, and recovery checks.

# Appendix B. Official references

- AWS CLI Command Reference: https://docs.aws.amazon.com/cli/latest/reference/
- AWS CLI `get-caller-identity`: https://docs.aws.amazon.com/cli/latest/reference/sts/get-caller-identity.html
- AWS CLI `assume-role`: https://docs.aws.amazon.com/cli/latest/reference/sts/assume-role.html
- KMS imported key material: https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys.html
- CloudHSM CLI reference: https://docs.aws.amazon.com/cloudhsm/latest/userguide/cloudhsm_cli-reference.html
- PowerShell documentation: https://learn.microsoft.com/powershell/
- OpenSSL documentation: https://docs.openssl.org/

Always verify current syntax using the installed tool's `--help` and the official documentation before a production change.
