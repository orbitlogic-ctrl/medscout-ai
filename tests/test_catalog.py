import json
from pathlib import Path

import pytest

from medscout import Facility, load_catalog


def test_bundled_catalog_loads_expected_cities_and_services() -> None:
    facilities = load_catalog()
    assert all(isinstance(facility, Facility) for facility in facilities)
    assert {facility.city for facility in facilities} == {
        "Bologna", "Modena", "Parma", "Reggio Emilia", "Ferrara",
    }
    assert {facility.region for facility in facilities} == {"Emilia-Romagna"}
    assert {service for facility in facilities for service in facility.services} == {
        "Dermatology consultation", "Cardiology consultation", "Abdominal ultrasound",
    }


def test_bundled_catalog_ids_are_unique() -> None:
    facilities = load_catalog()
    assert len({facility.id for facility in facilities}) == len(facilities)


def test_bundled_catalog_is_fictional_and_unverified() -> None:
    for facility in load_catalog():
        assert facility.name.startswith("Fictional ")
        assert facility.provenance == "synthetic"
        assert facility.verification_status == "unverified"


@pytest.fixture
def record() -> dict[str, object]:
    return {
        "id": "ms-test-001",
        "name": "Fictional Test Clinic",
        "city": "Bologna",
        "region": "Emilia-Romagna",
        "services": ["Dermatology consultation"],
        "provenance": "synthetic",
        "verification_status": "unverified",
    }


@pytest.mark.parametrize(
    "field",
    ["id", "name", "city", "region", "services", "provenance", "verification_status"],
)
def test_loader_rejects_missing_fields(
    monkeypatch: pytest.MonkeyPatch, record: dict[str, object], field: str
) -> None:
    del record[field]
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: json.dumps([record]))

    with pytest.raises(ValueError, match=field):
        load_catalog(Path("test-catalog.json"))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", " ", "name"),
        ("services", [], "services"),
        ("services", [42], "service"),
        ("provenance", "real", "provenance"),
        ("verification_status", "verified", "verification_status"),
    ],
)
def test_loader_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch, record: dict[str, object], field: str, value: object, message: str
) -> None:
    record[field] = value
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: json.dumps([record]))

    with pytest.raises(ValueError, match=message):
        load_catalog(Path("test-catalog.json"))


def test_loader_rejects_duplicate_ids(
    monkeypatch: pytest.MonkeyPatch, record: dict[str, object]
) -> None:
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: json.dumps([record, record]))

    with pytest.raises(ValueError, match="duplicate facility id"):
        load_catalog(Path("test-catalog.json"))
