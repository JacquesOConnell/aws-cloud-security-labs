from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from .models import Finding


ADMINISTRATOR_ACCESS_ARN = "arn:aws:iam::aws:policy/AdministratorAccess"


def _list_users(client: Any) -> Iterable[dict[str, Any]]:
    marker: str | None = None
    while True:
        request = {"Marker": marker} if marker else {}
        response = client.list_users(**request)
        yield from response.get("Users", [])
        if not response.get("IsTruncated"):
            return
        marker = response["Marker"]


def _has_console_password(client: Any, username: str) -> bool:
    try:
        client.get_login_profile(UserName=username)
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "NoSuchEntity":
            return False
        raise


def _list_access_keys(client: Any, username: str) -> Iterable[dict[str, Any]]:
    marker: str | None = None
    while True:
        request: dict[str, Any] = {"UserName": username}
        if marker:
            request["Marker"] = marker
        response = client.list_access_keys(**request)
        yield from response.get("AccessKeyMetadata", [])
        if not response.get("IsTruncated"):
            return
        marker = response["Marker"]


def _attached_user_policies(client: Any, username: str) -> list[dict[str, str]]:
    policies: list[dict[str, str]] = []
    marker: str | None = None
    while True:
        request: dict[str, Any] = {"UserName": username}
        if marker:
            request["Marker"] = marker
        response = client.list_attached_user_policies(**request)
        policies.extend(response.get("AttachedPolicies", []))
        if not response.get("IsTruncated"):
            return policies
        marker = response["Marker"]


def _group_names(client: Any, username: str) -> list[str]:
    groups: list[str] = []
    marker: str | None = None
    while True:
        request: dict[str, Any] = {"UserName": username}
        if marker:
            request["Marker"] = marker
        response = client.list_groups_for_user(**request)
        groups.extend(group["GroupName"] for group in response.get("Groups", []))
        if not response.get("IsTruncated"):
            return groups
        marker = response["Marker"]


def _group_has_administrator_access(client: Any, group_name: str) -> bool:
    marker: str | None = None
    while True:
        request: dict[str, Any] = {"GroupName": group_name}
        if marker:
            request["Marker"] = marker
        response = client.list_attached_group_policies(**request)
        if any(
            policy.get("PolicyArn") == ADMINISTRATOR_ACCESS_ARN
            for policy in response.get("AttachedPolicies", [])
        ):
            return True
        if not response.get("IsTruncated"):
            return False
        marker = response["Marker"]


def audit_iam(
    client: Any,
    *,
    now: datetime | None = None,
    access_key_max_age_days: int = 90,
) -> list[Finding]:
    """Audit IAM users with read-only IAM API calls."""

    now = now or datetime.now(UTC)
    findings: list[Finding] = []

    for user in _list_users(client):
        username = user["UserName"]

        if _has_console_password(client, username):
            mfa_devices = client.list_mfa_devices(UserName=username).get("MFADevices", [])
            if not mfa_devices:
                findings.append(
                    Finding(
                        severity="HIGH",
                        service="IAM",
                        region="global",
                        resource=username,
                        check_id="IAM_CONSOLE_MFA_MISSING",
                        title="IAM console user does not have MFA",
                        status="FAIL",
                        evidence="A login profile exists, but no MFA device is assigned.",
                        recommendation=(
                            "Require MFA, preferably phishing-resistant authentication, "
                            "or remove console access when it is unnecessary."
                        ),
                    )
                )

        for access_key in _list_access_keys(client, username):
            if access_key.get("Status") != "Active":
                continue
            created = access_key["CreateDate"]
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_days = (now - created).days
            if age_days > access_key_max_age_days:
                findings.append(
                    Finding(
                        severity="HIGH",
                        service="IAM",
                        region="global",
                        resource=username,
                        check_id="IAM_ACCESS_KEY_AGE",
                        title="Active IAM access key exceeds the age threshold",
                        status="FAIL",
                        evidence=(
                            f"Access key ending in {access_key['AccessKeyId'][-4:]} "
                            f"is {age_days} days old."
                        ),
                        recommendation=(
                            "Replace long-lived user keys with temporary role credentials. "
                            "If a key is still required, rotate it using a tested process."
                        ),
                    )
                )

        attached = _attached_user_policies(client, username)
        if any(
            policy.get("PolicyArn") == ADMINISTRATOR_ACCESS_ARN
            for policy in attached
        ):
            findings.append(
                Finding(
                    severity="CRITICAL",
                    service="IAM",
                    region="global",
                    resource=username,
                    check_id="IAM_DIRECT_ADMIN_POLICY",
                    title="AdministratorAccess is attached directly to an IAM user",
                    status="FAIL",
                    evidence="AWS managed AdministratorAccess is attached to the user.",
                    recommendation=(
                        "Remove direct administrator access and use a controlled role with "
                        "temporary credentials, MFA and least-privilege permissions."
                    ),
                )
            )

        inline_user_policies = client.list_user_policies(UserName=username).get(
            "PolicyNames", []
        )
        if inline_user_policies:
            findings.append(
                Finding(
                    severity="MEDIUM",
                    service="IAM",
                    region="global",
                    resource=username,
                    check_id="IAM_INLINE_USER_POLICY",
                    title="IAM user has inline policies",
                    status="REVIEW",
                    evidence=f"Inline policies: {', '.join(inline_user_policies)}.",
                    recommendation=(
                        "Review effective permissions and prefer centrally managed policies "
                        "or role-based access where practical."
                    ),
                )
            )

        admin_groups = [
            group
            for group in _group_names(client, username)
            if _group_has_administrator_access(client, group)
        ]
        if admin_groups:
            findings.append(
                Finding(
                    severity="CRITICAL",
                    service="IAM",
                    region="global",
                    resource=username,
                    check_id="IAM_GROUP_ADMIN_POLICY",
                    title="IAM user receives AdministratorAccess through a group",
                    status="FAIL",
                    evidence=f"Administrator groups: {', '.join(admin_groups)}.",
                    recommendation=(
                        "Replace standing administrator membership with an assumable, "
                        "MFA-protected role and time-bounded sessions."
                    ),
                )
            )

    return findings


