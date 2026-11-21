"""Load and validate the synthetic healthcare facilities catalog."""

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class Facility:
    """A fictional facility and its example services."""

    id: str
    name: str
    city: str
    region: str
    services: tuple[str, ...]
    provenance: Literal["synthetic"]
    verification_status: Literal["unverified"]


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} must be non-empty text without surrounding whitespace")
    return value


def _parse_facility(record: object) -> Facility:
    if not isinstance(record, dict):
        raise ValueError("each facility must be an object")

    services = record.get("services")
    if not isinstance(services, list) or not services:
        raise ValueError("services must be a non-empty array")
    if record.get("provenance") != "synthetic":
        raise ValueError("provenance must be synthetic")
    if record.get("verification_status") != "unverified":
        raise ValueError("verification_status must be unverified")

    return Facility(
        id=_required_text(record.get("id"), "id"),
        name=_required_text(record.get("name"), "name"),
        city=_required_text(record.get("city"), "city"),
        region=_required_text(record.get("region"), "region"),
        services=tuple(_required_text(service, "service") for service in services),
        provenance="synthetic",
        verification_status="unverified",
    )


def load_catalog(path: Path | None = None) -> tuple[Facility, ...]:
    """Load bundled data or a local JSON file, raising ValueError for invalid data."""
    source = path if path is not None else files("medscout").joinpath("data", "facilities.json")
    records: object = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("catalog must be a non-empty array of facilities")

    facilities: list[Facility] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        try:
            facility = _parse_facility(record)
        except ValueError as error:
            raise ValueError(f"facility {index}: {error}") from error
        if facility.id in seen_ids:
            raise ValueError(f"duplicate facility id: {facility.id}")
        seen_ids.add(facility.id)
        facilities.append(facility)

    return tuple(facilities)
