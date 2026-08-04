from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError

from aws_security_auditor.iam_checks import audit_iam


class FakeIamClient:
    def list_users(self, **_kwargs):
        return {
            "Users": [{"UserName": "admin-user"}, {"UserName": "service-user"}],
            "IsTruncated": False,
        }

    def get_login_profile(self, UserName):
        if UserName == "service-user":
            raise ClientError(
                {"Error": {"Code": "NoSuchEntity", "Message": "No login profile"}},
                "GetLoginProfile",
            )
        return {"LoginProfile": {"UserName": UserName}}

    def list_mfa_devices(self, **_kwargs):
        return {"MFADevices": []}

    def list_access_keys(self, UserName, **_kwargs):
        if UserName == "service-user":
            return {"AccessKeyMetadata": [], "IsTruncated": False}
        return {
            "AccessKeyMetadata": [
                {
                    "AccessKeyId": "AKIATEST1234",
                    "Status": "Active",
                    "CreateDate": datetime(2025, 1, 1, tzinfo=UTC),
                }
            ],
            "IsTruncated": False,
        }

    def list_attached_user_policies(self, UserName, **_kwargs):
        policies = []
        if UserName == "admin-user":
            policies.append(
                {
                    "PolicyName": "AdministratorAccess",
                    "PolicyArn": "arn:aws:iam::aws:policy/AdministratorAccess",
                }
            )
        return {"AttachedPolicies": policies, "IsTruncated": False}

    def list_user_policies(self, UserName):
        return {"PolicyNames": ["LegacyInline"] if UserName == "admin-user" else []}

    def list_groups_for_user(self, UserName, **_kwargs):
        groups = [{"GroupName": "Admins"}] if UserName == "admin-user" else []
        return {"Groups": groups, "IsTruncated": False}

    def list_attached_group_policies(self, GroupName, **_kwargs):
        assert GroupName == "Admins"
        return {
            "AttachedPolicies": [
                {
                    "PolicyName": "AdministratorAccess",
                    "PolicyArn": "arn:aws:iam::aws:policy/AdministratorAccess",
                }
            ],
            "IsTruncated": False,
        }


def test_audit_iam_detects_console_key_and_policy_risks():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    findings = audit_iam(FakeIamClient(), now=now)

    finding_ids = {finding.check_id for finding in findings}
    assert finding_ids == {
        "IAM_CONSOLE_MFA_MISSING",
        "IAM_ACCESS_KEY_AGE",
        "IAM_DIRECT_ADMIN_POLICY",
        "IAM_INLINE_USER_POLICY",
        "IAM_GROUP_ADMIN_POLICY",
    }

    access_key_finding = next(
        finding for finding in findings if finding.check_id == "IAM_ACCESS_KEY_AGE"
    )
    assert "1234" in access_key_finding.evidence
    assert access_key_finding.severity == "HIGH"


