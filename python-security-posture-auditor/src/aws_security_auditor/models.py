from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    """A normalized security observation produced by an audit check."""

    severity: str
    service: str
    region: str
    resource: str
    check_id: str
    title: str
    status: str
    evidence: str
    recommendation: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


