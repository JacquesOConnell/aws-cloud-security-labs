from aws_security_auditor.kms_checks import audit_kms


class FakeKmsClient:
    def list_keys(self, **_kwargs):
        return {
            "Keys": [
                {"KeyId": "aws-generated"},
                {"KeyId": "external-key"},
                {"KeyId": "disabled-key"},
            ],
            "Truncated": False,
        }

    def list_aliases(self, **_kwargs):
        return {
            "Aliases": [
                {"AliasName": "alias/app", "TargetKeyId": "aws-generated"},
                {"AliasName": "alias/byok", "TargetKeyId": "external-key"},
                {"AliasName": "alias/old", "TargetKeyId": "disabled-key"},
            ],
            "Truncated": False,
        }

    def describe_key(self, KeyId):
        metadata = {
            "aws-generated": {
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
                "Origin": "AWS_KMS",
                "KeySpec": "SYMMETRIC_DEFAULT",
                "KeyUsage": "ENCRYPT_DECRYPT",
            },
            "external-key": {
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
                "Origin": "EXTERNAL",
                "KeySpec": "SYMMETRIC_DEFAULT",
                "KeyUsage": "ENCRYPT_DECRYPT",
            },
            "disabled-key": {
                "KeyManager": "CUSTOMER",
                "KeyState": "Disabled",
                "Origin": "AWS_KMS",
                "KeySpec": "SYMMETRIC_DEFAULT",
                "KeyUsage": "ENCRYPT_DECRYPT",
            },
        }
        return {"KeyMetadata": metadata[KeyId]}

    def get_key_rotation_status(self, KeyId):
        return {"KeyRotationEnabled": KeyId != "aws-generated"}


def test_audit_kms_classifies_rotation_external_and_disabled_keys():
    findings = audit_kms(FakeKmsClient(), "af-south-1")

    finding_ids = {finding.check_id for finding in findings}
    assert finding_ids == {
        "KMS_ROTATION_DISABLED",
        "KMS_EXTERNAL_ORIGIN",
        "KMS_KEY_STATE",
    }

    high_finding = next(
        finding for finding in findings if finding.check_id == "KMS_KEY_STATE"
    )
    assert high_finding.severity == "HIGH"
    assert high_finding.resource == "alias/old"


