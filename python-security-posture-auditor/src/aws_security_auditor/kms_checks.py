from collections.abc import Iterable
from typing import Any

from botocore.exceptions import ClientError

from .models import Finding


def _list_keys(client: Any) -> Iterable[dict[str, str]]:
    """Yield every KMS key while handling API pagination."""

    marker: str | None = None
    while True:
        request: dict[str, Any] = {"Limit": 1000}
        if marker:
            request["Marker"] = marker

        response = client.list_keys(**request)
        yield from response.get("Keys", [])

        if not response.get("Truncated"):
            return
        marker = response["NextMarker"]


def _alias_map(client: Any) -> dict[str, str]:
    """Return key ID to alias name mappings for human-readable reports."""

    aliases: dict[str, str] = {}
    marker: str | None = None
    while True:
        request: dict[str, Any] = {"Limit": 100}
        if marker:
            request["Marker"] = marker

        response = client.list_aliases(**request)
        for alias in response.get("Aliases", []):
            key_id = alias.get("TargetKeyId")
            alias_name = alias.get("AliasName")
            if key_id and alias_name:
                aliases[key_id] = alias_name

        if not response.get("Truncated"):
            return aliases
        marker = response["NextMarker"]


def _rotation_enabled(client: Any, key_id: str) -> bool | None:
    """Return automatic rotation state, or None when the API is unsupported."""

    try:
        response = client.get_key_rotation_status(KeyId=key_id)
        return bool(response.get("KeyRotationEnabled"))
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "Unknown")
        if code in {
            "AccessDeniedException",
            "DisabledException",
            "KMSInvalidStateException",
            "UnsupportedOperationException",
        }:
            return None
        raise


def audit_kms(client: Any, region: str) -> list[Finding]:
    """Inspect KMS metadata without performing cryptographic operations."""

    findings: list[Finding] = []
    aliases = _alias_map(client)

    for key in _list_keys(client):
        key_id = key["KeyId"]
        metadata = client.describe_key(KeyId=key_id)["KeyMetadata"]

        key_manager = metadata.get("KeyManager", "UNKNOWN")
        state = metadata.get("KeyState", "UNKNOWN")
        origin = metadata.get("Origin", "UNKNOWN")
        key_spec = metadata.get("KeySpec", "UNKNOWN")
        key_usage = metadata.get("KeyUsage", "UNKNOWN")
        resource = aliases.get(key_id, key_id)

        if state != "Enabled":
            findings.append(
                Finding(
                    severity="HIGH",
                    service="KMS",
                    region=region,
                    resource=resource,
                    check_id="KMS_KEY_STATE",
                    title="KMS key is not enabled",
                    status="FAIL",
                    evidence=f"Key state is {state}; origin is {origin}.",
                    recommendation=(
                        "Confirm whether this state is intentional. Investigate pending "
                        "deletion, disabled keys, or missing imported material."
                    ),
                )
            )

        if key_manager != "CUSTOMER":
            continue

        if origin == "EXTERNAL":
            findings.append(
                Finding(
                    severity="INFO",
                    service="KMS",
                    region=region,
                    resource=resource,
                    check_id="KMS_EXTERNAL_ORIGIN",
                    title="KMS key uses imported key material",
                    status="REVIEW",
                    evidence=f"Origin is EXTERNAL and state is {state}.",
                    recommendation=(
                        "Verify external custody, durability, expiration monitoring and "
                        "tested reimport procedures for the original material."
                    ),
                )
            )
            continue

        supports_automatic_rotation = (
            origin == "AWS_KMS"
            and key_spec == "SYMMETRIC_DEFAULT"
            and key_usage == "ENCRYPT_DECRYPT"
        )
        if supports_automatic_rotation:
            rotation = _rotation_enabled(client, key_id)
            if rotation is False:
                findings.append(
                    Finding(
                        severity="MEDIUM",
                        service="KMS",
                        region=region,
                        resource=resource,
                        check_id="KMS_ROTATION_DISABLED",
                        title="Automatic KMS key rotation is disabled",
                        status="FAIL",
                        evidence="Key is customer managed, symmetric and AWS-generated.",
                        recommendation=(
                            "Enable automatic rotation unless a documented exception or "
                            "application-specific rotation process applies."
                        ),
                    )
                )

    return findings


