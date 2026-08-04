# AWS KMS BYOK Lab and Interview Guide

This lab demonstrates the complete lifecycle of customer-supplied key material in AWS Key Management Service (AWS KMS): external generation, transport wrapping, import, use, deletion, reimport and audit.

> **Security notice:** All identifiers and outputs in this guide are sanitized. Never commit plaintext key material, import tokens, wrapping parameters, ciphertext samples, credentials, account IDs or live KMS key ARNs.

## 1. Outcome

The lab implemented the following workflow:

```text
Generate 256-bit AES material outside AWS
                  |
                  v
Download temporary RSA wrapping public key and import token
                  |
                  v
Wrap the AES material with RSA-OAEP SHA-256
                  |
                  v
Import into an EXTERNAL-origin KMS key
                  |
                  v
Encrypt and decrypt with an authenticated encryption context
                  |
                  v
Delete imported material -> key becomes unusable
                  |
                  v
Rewrap the same material with new import parameters
                  |
                  v
Reimport as EXISTING_KEY_MATERIAL -> access is restored
```

## 2. Core concepts

### Logical KMS key versus key material

The KMS key is a logical resource containing an ID, alias, policy, metadata and references to cryptographic material. With an `EXTERNAL` origin, AWS creates the logical key without generating the underlying material.

Before import:

```text
Origin:   EXTERNAL
State:    PendingImport
Usable:   No
```

After a successful import:

```text
Origin:   EXTERNAL
State:    Enabled
Usable:   Yes
```

The origin is immutable. An `EXTERNAL`-origin key cannot later be converted to AWS-generated material.

### Responsibility boundary

AWS KMS protects imported material while it is in the service, but the customer remains responsible for:

- generating the material using an approved source of randomness;
- retaining an authoritative recoverable copy;
- controlling custody outside AWS;
- planning expiration and reimport procedures;
- preventing accidental loss;
- demonstrating auditability and separation of duties.

For this proof of concept, OpenSSL generated the material locally. Production BYOK material should normally originate from an approved HSM or enterprise key-management system.

## 3. Lab configuration

| Setting | Lab value |
|---|---|
| Region | `af-south-1` |
| Key type | Symmetric |
| Key usage | Encrypt and decrypt |
| Key origin | External - imported key material |
| Regionality | Single Region |
| Alias | `alias/personal-byok-lab` |
| Imported material | 256-bit AES key (32 random bytes) |
| Wrapping key | RSA 4096 |
| Wrapping algorithm | RSAES OAEP SHA-256 |
| Expiration | Does not expire for the short lab |

## 4. Sensitive-file model

| File | Purpose | Handling |
|---|---|---|
| `PlaintextKeyMaterial.bin` | Original 32-byte AES material | **Critical secret; never upload or commit** |
| `WrappingPublicKey.bin` | Temporary KMS public key used for transport wrapping | Not secret, but temporary and key-specific |
| `ImportToken.bin` | Binds an import to the KMS key and import parameters | Temporary; never publish |
| `EncryptedKeyMaterial.bin` | AES material wrapped for transport to KMS | Do not publish |
| `byok-ciphertext.bin` | KMS ciphertext used for testing | Not plaintext, but omit from a public lab repository |
| `README.txt` | KMS-generated parameter and expiration information | Sanitize before sharing |

The wrapping public key and import token are a matched set and expire after 24 hours. Every import or reimport requires a newly downloaded set.

## 5. Create the external-origin KMS key

In **AWS KMS > Customer managed keys**, create a symmetric encryption key with:

```text
Key material origin: External - Import key material
Alias:               personal-byok-lab
```

The initial state is `PendingImport` because the logical key exists without cryptographic material.

## 6. Download import parameters

Choose:

```text
Wrapping key specification: RSA_4096
Wrapping algorithm:         RSAES_OAEP_SHA_256
```

Download and extract the archive. It contains:

```text
WrappingPublicKey.bin
ImportToken.bin
README.txt
```

RSA-4096 was selected as the longest practical wrapping key, and OAEP with SHA-256 provided modern padding and hashing for transport protection.

## 7. Generate external AES material

PowerShell using Git for Windows OpenSSL:

```powershell
$OpenSSL = "C:\Program Files\Git\usr\bin\openssl.exe"
& $OpenSSL rand -out PlaintextKeyMaterial.bin 32
```

Verify only the length; never display the material:

```powershell
Get-Item ".\PlaintextKeyMaterial.bin" |
    Select-Object Name, Length
```

Expected length: `32` bytes, or 256 bits.

## 8. Wrap the material for transport

The wrapping algorithm used during encryption must match the algorithm selected when the import parameters were downloaded.

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

With an RSA-4096 wrapping key, the wrapped output is normally 512 bytes.

Only `EncryptedKeyMaterial.bin` and `ImportToken.bin` are uploaded. The plaintext material never travels to AWS in unwrapped form.

## 9. Import and enable the key

Upload the wrapped material and its matched import token. After a successful initial import:

```text
PendingImport -> Enabled
```

KMS unwraps the material using the private wrapping key inside a KMS HSM and protects the imported material within the KMS service boundary.

## 10. Encrypt with an encryption context

Create test data:

```powershell
Set-Content `
    -Path ".\byok-plaintext.txt" `
    -Value "AWS KMS BYOK lab test" `
    -Encoding ascii `
    -NoNewline
```

Encrypt it:

```powershell
$EncryptResult = aws kms encrypt `
    --region af-south-1 `
    --key-id alias/personal-byok-lab `
    --plaintext fileb://byok-plaintext.txt `
    --encryption-context Purpose=BYOKLab `
    --output json | ConvertFrom-Json

[IO.File]::WriteAllBytes(
    (Join-Path $PWD "byok-ciphertext.bin"),
    [Convert]::FromBase64String([string]$EncryptResult.CiphertextBlob)
)
```

The encryption context is non-secret authenticated additional data. The exact same key-value pairs are required during decryption.

## 11. Decrypt and test context enforcement

```powershell
$DecryptResult = aws kms decrypt `
    --region af-south-1 `
    --ciphertext-blob fileb://byok-ciphertext.bin `
    --encryption-context Purpose=BYOKLab `
    --output json | ConvertFrom-Json

[Text.Encoding]::ASCII.GetString(
    [Convert]::FromBase64String([string]$DecryptResult.Plaintext)
)
```

Supplying a different context produced `InvalidCiphertextException`, proving that the context was cryptographically bound to the operation.

## 12. Demonstrate cryptographic erasure

Delete only the imported material, not the logical KMS key.

Expected result:

```text
Enabled -> PendingImport
```

The existing ciphertext then becomes inaccessible because KMS no longer has the material required to decrypt it.

> Deleting the entire KMS key would be different. Recreating another KMS key and importing the same bytes would not restore KMS ciphertext bound to the original logical key.

## 13. Reimport and restore access

Download a new wrapping public key and import token. Rewrap the **same** original `PlaintextKeyMaterial.bin`:

```powershell
& $OpenSSL pkeyutl `
    -encrypt `
    -in ".\PlaintextKeyMaterial.bin" `
    -out ".\reimport-parameters\ReimportEncryptedKeyMaterial.bin" `
    -inkey ".\reimport-parameters\WrappingPublicKey.bin" `
    -keyform DER `
    -pubin `
    -pkeyopt rsa_padding_mode:oaep `
    -pkeyopt rsa_oaep_md:sha256 `
    -pkeyopt rsa_mgf1_md:sha256
```

The console initially attempted to import the material as `NEW_KEY_MATERIAL` and returned `IncorrectKeyMaterialException`. This was useful evidence: KMS recognized that the material was already permanently associated with the key.

The correct operation was explicit reimport:

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

The key returned to `Enabled`, and the ciphertext created before deletion decrypted successfully. This proved that the identical external material restored access without re-encrypting the data.

## 14. New material versus existing material

| Import type | Meaning |
|---|---|
| `NEW_KEY_MATERIAL` | Associates genuinely new material for supported rotation workflows |
| `EXISTING_KEY_MATERIAL` | Reimports material already associated with the KMS key |

For imported symmetric keys that support on-demand rotation, AWS KMS can associate multiple key materials. Reimporting deleted or expired material is not the same as introducing material for rotation.

## 15. CloudTrail audit evidence

The lab observed the following event types:

```text
GetParametersForImport
ImportKeyMaterial
DeleteImportedKeyMaterial
Encrypt
Decrypt
```

Query example:

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
        --query "Events[].{Time:EventTime,Event:EventName,User:Username}" `
        --output table
}
```

Multiple `ImportKeyMaterial` entries can include failed attempts. Inspecting the individual CloudTrail event JSON reveals fields such as `errorCode` and `errorMessage`.

## 16. Production considerations

### Key generation and custody

- Generate production material in an approved HSM or enterprise key-management system.
- Maintain protected, tested recovery copies outside AWS.
- Use dual control, split knowledge or quorum controls where required.
- Document custodians, access reviews and key ceremonies.

### Availability and durability

- AWS cannot recreate customer-supplied material.
- Losing the external copy can make ciphertext permanently unrecoverable after deletion or expiration.
- Test reimport before relying on expiration as an operational control.
- Alert well before expiration and automate safe renewal workflows.

### Access control

- Separate key administrators from key users.
- Restrict `kms:GetParametersForImport`, `kms:ImportKeyMaterial` and `kms:DeleteImportedKeyMaterial`.
- Use key policies, IAM conditions and service-specific encryption contexts.
- Avoid long-lived IAM user credentials.

### Monitoring

- Retain CloudTrail management and data-event evidence as required.
- Alert on imported-material deletion, reimport, policy changes and deletion scheduling.
- Send security logs to a protected central logging account or SIEM.

## 17. Troubleshooting record

### Ciphertext file was missing

**Cause:** The AWS CLI response had not been captured and decoded into a binary file.

**Resolution:** Capture JSON with `ConvertFrom-Json`, decode `CiphertextBlob` from Base64, and write it with `WriteAllBytes`.

### Wrong encryption context

**Symptom:** `InvalidCiphertextException`.

**Meaning:** Decryption did not supply the same authenticated context used during encryption.

### Reimport rejected as new material

**Symptom:** `IncorrectKeyMaterialException` stated that the material was already associated with the KMS key.

**Cause:** The console attempted `NEW_KEY_MATERIAL` instead of reimporting existing material.

**Resolution:** Invoke `ImportKeyMaterial` with `--import-type EXISTING_KEY_MATERIAL`.

## 18. Cleanup

1. Delete the imported material.
2. Confirm the key returns to `PendingImport`.
3. Schedule deletion of the exact lab KMS key using the minimum waiting period appropriate for the lab.
4. Remove plaintext key material, wrapping parameters, import tokens, wrapped copies and test ciphertext from the workstation.
5. Verify no sensitive artifacts were staged or committed to Git.

## 19. Interview questions and model answers

### What is BYOK in AWS KMS?

BYOK allows a customer to create a KMS key with an `EXTERNAL` origin and import cryptographic material generated outside AWS. AWS KMS performs cryptographic operations with the material, while the customer retains responsibility for its external generation, custody, availability and recovery.

### Why use imported material?

Typical reasons include regulatory requirements, centralized enterprise key generation, documented key ceremonies, external custody requirements, or the ability to remove material from AWS on demand. It adds operational risk and should not be used when AWS-generated material already satisfies the requirement.

### Is imported KMS material the same as CloudHSM?

No. Imported KMS material is used through standard KMS APIs and integrated AWS services. CloudHSM provides dedicated, single-tenant HSMs and direct interfaces such as PKCS #11, JCE and OpenSSL. CloudHSM also requires more customer-managed networking, users, availability and operations.

### What happens when imported material is deleted?

The KMS key becomes unusable and normally transitions to `PendingImport`. Existing ciphertext remains stored but cannot be decrypted until the identical material is reimported into the same logical KMS key.

### Why can the material not be imported into a new KMS key to recover old ciphertext?

AWS KMS ciphertext is bound to the logical KMS key, not only to the raw key bytes. The original key identity and the original material are both required.

### What is the role of the wrapping public key?

It encrypts the customer material for transport to KMS. Its corresponding private key remains protected in a KMS HSM. The wrapping key and import token are temporary, matched and valid for a limited period.

### What did the troubleshooting teach you?

The lab exposed the difference between importing genuinely new material for rotation and reimporting material already associated with a key. AWS rejected the existing material under `NEW_KEY_MATERIAL`; explicitly using `EXISTING_KEY_MATERIAL` restored the deleted material and recovered access.

## 20. Interview-ready summary

> I completed an AWS KMS BYOK lab using a symmetric external-origin key. I generated 256-bit AES material locally, wrapped it using an RSA-4096 KMS wrapping key with RSA-OAEP SHA-256, and imported it into KMS. I tested encryption and decryption with an authenticated encryption context, deleted the imported material to make the key unusable, and reimported the identical material to restore access to existing ciphertext. I also used CloudTrail to audit the import, deletion and cryptographic operations, and I documented the production requirements for HSM-based generation, external custody, separation of duties, expiration monitoring and tested recovery.

## 21. Official references

- [Importing key material for AWS KMS keys](https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys.html)
- [Create a KMS key with imported key material](https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys-conceptual.html)
- [Download the wrapping public key and import token](https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys-get-public-key-and-token.html)
- [Encrypt the key material](https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys-encrypt-key-material.html)
- [Import and reimport key material](https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys-import-key-material.html)
- [Special considerations for imported key material](https://docs.aws.amazon.com/kms/latest/developerguide/importing-keys-considerations.html)

