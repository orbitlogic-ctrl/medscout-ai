from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

import pytest

from medscout import load_catalog
from medscout.__main__ import main
from medscout.search import (
    BookableSlot,
    BookingChannel,
    Coordinates,
    FacilitySite,
    Price,
    Practitioner,
    ReviewSummary,
    SearchQuery,
    ServiceOffering,
    SourceMetadata,
    WaitingTimeStatistic,
    haversine_km,
    offerings_from_catalog,
    search_offerings,
    search_offerings_with_details,
)


@pytest.fixture
def offering() -> ServiceOffering:
    source = SourceMetadata("synthetic", "unverified")
    site = FacilitySite(
        "test-site", "Fictional Test Clinic", "Reggio Emilia", "Emilia-Romagna",
        source, province="Reggio Emilia", coordinates=Coordinates(0, 1),
    )
    return ServiceOffering(
        "test-offering", site, "Cardiology Consultation", price=Price(Decimal("42"), " eur ")
    )


def test_search_combines_normalized_filters(offering: ServiceOffering) -> None:
    query = SearchQuery(
        service_name="  CARDIOLOGY\t consultation ", city=" reggio   EMILIA ",
        province="REGGIO\tEMILIA", max_price=Decimal("42"), currency=" eur ",
        origin=Coordinates(0, 1), radius_km=0,
    )
    [result] = search_offerings(iter([offering]), query)
    assert result.offering is offering
    assert result.distance_km == 0


@pytest.mark.parametrize(
    "query",
    [
        SearchQuery(service_name="dermatology"),
        SearchQuery(city="Reggio"),
        SearchQuery(province="Parma"),
        SearchQuery(max_price=Decimal("41.99")),
        SearchQuery(max_price=Decimal("999"), currency="USD"),
        SearchQuery(origin=Coordinates(0, 0), radius_km=30),
    ],
)
def test_each_filter_can_exclude_an_offering(offering: ServiceOffering, query: SearchQuery) -> None:
    assert search_offerings([offering], query) == ()


def test_blank_filters_and_casefold(offering: ServiceOffering) -> None:
    item = replace(offering, service_name="Straße screening")
    assert search_offerings([item], SearchQuery(service_name="STRASSE", city=" \t "))
    assert search_offerings([], SearchQuery()) == ()


def test_missing_metadata_does_not_meet_an_explicit_filter(offering: ServiceOffering) -> None:
    unknown = replace(offering, price=None, facility=replace(offering.facility, province=None, coordinates=None))
    assert search_offerings([unknown], SearchQuery())[0].offering.bookable_slots is None
    assert not search_offerings([unknown], SearchQuery(max_price=Decimal("0")))
    assert not search_offerings([unknown], SearchQuery(province="Reggio Emilia"))
    assert not search_offerings([unknown], SearchQuery(origin=Coordinates(0, 0), radius_km=30))
    free = replace(unknown, price=Price(Decimal("0"), "EUR"))
    assert search_offerings([free], SearchQuery(max_price=Decimal("0")))


def test_haversine_uses_kilometers_and_handles_antimeridian() -> None:
    assert haversine_km(Coordinates(0, 0), Coordinates(0, 1)) == pytest.approx(111.195, abs=0.001)
    assert haversine_km(Coordinates(0, 179), Coordinates(0, -179)) == pytest.approx(222.390, abs=0.001)
    assert haversine_km(Coordinates(0, 0), Coordinates(0, 180)) == pytest.approx(20015.114, abs=0.001)


def test_radius_is_inclusive_and_results_are_deterministic(offering: ServiceOffering) -> None:
    origin = Coordinates(0, 0)
    boundary = haversine_km(origin, Coordinates(0, 1))
    near = replace(offering, id="near", facility=replace(offering.facility, coordinates=Coordinates(0, 0.1)))
    tied = replace(offering, id="a-tie")
    missing = replace(offering, id="unknown", facility=replace(offering.facility, coordinates=None))
    items = [missing, offering, tied, near]
    expected = ["near", "a-tie", "test-offering", "unknown"]

    for source in (items, reversed(items)):
        results = search_offerings(source, SearchQuery(origin=origin))
        assert [result.offering.id for result in results] == expected
        assert results[-1].distance_km is None
    results = search_offerings(items, SearchQuery(origin=origin, radius_km=boundary))
    assert [result.offering.id for result in results] == expected[:-1]


@pytest.mark.parametrize("lat, lon", [(91, 0), (0, -181), (float("nan"), 0), (0, float("inf"))])
def test_invalid_coordinates_raise(lat: float, lon: float) -> None:
    with pytest.raises(ValueError, match="latitude"):
        Coordinates(lat, lon)


@pytest.mark.parametrize("radius", [-1, float("inf"), float("nan")])
def test_invalid_radius_raises(radius: float) -> None:
    with pytest.raises(ValueError, match="radius"):
        SearchQuery(origin=Coordinates(0, 0), radius_km=radius)


def test_radius_requires_origin() -> None:
    with pytest.raises(ValueError, match="requires origin"):
        SearchQuery(radius_km=30)


@pytest.mark.parametrize("amount", ["-0.01", "NaN", "Infinity"])
def test_invalid_price_limit_raises(amount: str) -> None:
    with pytest.raises(ValueError, match="price"):
        SearchQuery(max_price=Decimal(amount))


def test_invalid_currency_raises() -> None:
    with pytest.raises(ValueError, match="three-letter"):
        SearchQuery(max_price=Decimal("1"), currency="euros")


def test_preserves_pathways_and_metadata_without_inferring_slots(offering: ServiceOffering) -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    source = SourceMetadata("test-fixture", "verified", "https://example.invalid/source", checked)
    channel = BookingChannel("website", "https://example.invalid/book", source)
    ssn = replace(
        offering,
        id="ssn",
        pathway="ssn",
        source=source,
        facility=replace(offering.facility, address="Fictional test address"),
        practitioners=(Practitioner("test-practitioner", "Fictional Test Practitioner", source),),
        waiting_time=WaitingTimeStatistic(15, "median", checked, source),
        reviews=ReviewSummary(Decimal("4"), Decimal("5"), 2, source),
        booking_channels=(channel,),
    )
    private = replace(
        offering, id="private", pathway="private",
        bookable_slots=(BookableSlot(checked, channel, checked),),
    )
    results = search_offerings([ssn, private], SearchQuery(service_name="cardiology"))
    assert [result.offering for result in results] == [private, ssn]
    assert results[0].offering.bookable_slots == private.bookable_slots
    assert results[1].offering.bookable_slots is None
    assert results[1].offering.source is source


def test_legacy_adapter_preserves_ids_and_unknowns() -> None:
    catalog = load_catalog()
    results = offerings_from_catalog(catalog)
    assert len(results) == sum(len(facility.services) for facility in catalog)
    assert {item.facility.id for item in results} == {facility.id for facility in catalog}
    assert len({item.id for item in results}) == len(results)
    assert {item.id for item in offerings_from_catalog(reversed(catalog))} == {item.id for item in results}
    for item in results:
        assert item.facility.source == SourceMetadata("synthetic", "unverified")
        assert item.facility.province is item.facility.address is item.facility.coordinates is None
        assert item.price is item.waiting_time is item.bookable_slots is item.pathway is None


def test_adapter_deduplicates_normalized_legacy_services() -> None:
    [facility] = load_catalog()[:1]
    first_service = facility.services[0]
    duplicate = replace(facility, services=(first_service, f"  {first_service.upper()}  "))
    [item] = offerings_from_catalog([duplicate])
    assert item.service_name == first_service


def test_legacy_offering_ids_handle_separators() -> None:
    [facility] = load_catalog()[:1]
    records = (
        replace(facility, id="example:group", services=("screening",)),
        replace(facility, id="example", services=("group:screening",)),
    )
    assert len({item.id for item in offerings_from_catalog(records)}) == 2


def test_cli_module_entrypoint() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "medscout", "--service", " dermatology ", "--city", " Bologna "],
        cwd=Path(__file__).resolve().parents[1] / "src",
        capture_output=True, text=True, check=True,
    )
    assert "Synthetic data only" in completed.stdout
    assert "Fictional Bubble Comet Clinic" in completed.stdout
    assert "Price: unknown" in completed.stdout
    assert "Distance: not requested" in completed.stdout


@pytest.mark.parametrize(
    "query",
    [
        SearchQuery(service_name="dermatology", max_price=Decimal("50")),
        SearchQuery(city="Atlantis", max_price=Decimal("50")),
        SearchQuery(province="Parma", max_price=Decimal("50")),
        SearchQuery(province="Reggio Emilia", max_price=Decimal("41")),
        SearchQuery(max_price=Decimal("50"), origin=Coordinates(0, 0), radius_km=30),
    ],
)
def test_known_mismatch_excludes_candidate_despite_unknown_fields(
    offering: ServiceOffering, query: SearchQuery
) -> None:
    item = offering
    if query.max_price == Decimal("41"):
        item = replace(item, facility=replace(item.facility, province=None))
    else:
        item = replace(item, price=None)
    response = search_offerings_with_details([item], query)

    assert response.matches == ()
    assert response.uncertain_candidates == ()


def test_mixed_matches_and_uncertain_candidates_are_ordered(offering: ServiceOffering) -> None:
    site = replace(offering.facility, province=None, coordinates=None)
    unknown = replace(offering, id="first", facility=site, price=None)
    other_unknown = replace(unknown, id="second")
    priced_wrong_currency = replace(unknown, price=Price(Decimal("1"), "USD"))
    query = SearchQuery(
        province="Reggio Emilia", max_price=Decimal("42"),
        origin=Coordinates(0, 1), radius_km=10,
    )
    items = [other_unknown, priced_wrong_currency, offering, unknown]

    for source in (items, reversed(items)):
        response = search_offerings_with_details(source, query)
        assert [result.offering for result in response.matches] == [offering]
        assert [result.offering for result in response.uncertain_candidates] == [unknown, other_unknown]
        assert all(
            result.missing_data == ("province", "price", "coordinates")
            for result in response.uncertain_candidates
        )
    assert search_offerings(items, query) == response.matches


@pytest.mark.parametrize(
    ("filter_args", "missing_field", "message"),
    [
        (["--max-price", "50"], "price", "maximum price filter requires a recorded price"),
        (["--province", "Modena"], "province", "province filter requires a recorded province"),
        (
            ["--origin", "44", "11", "--radius-km", "30"],
            "coordinates",
            "radius filter requires facility coordinates",
        ),
    ],
)
def test_missing_filter_data_is_reported_in_response_and_cli(
    filter_args: list[str], missing_field: str, message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    query = {
        "price": SearchQuery(service_name="cardiology", city="Modena", max_price=Decimal("50")),
        "province": SearchQuery(service_name="cardiology", city="Modena", province="Modena"),
        "coordinates": SearchQuery(
            service_name="cardiology", city="Modena", origin=Coordinates(44, 11), radius_km=30,
        ),
    }[missing_field]
    response = search_offerings_with_details(offerings_from_catalog(load_catalog()), query)
    assert response.matches == ()
    [candidate] = response.uncertain_candidates
    assert candidate.missing_data == (missing_field,)
    assert candidate.offering.facility.id == "ms-syn-002"

    assert main(["--service", "cardiology", "--city", "Modena", *filter_args]) == 0
    output = capsys.readouterr().out
    assert "Synthetic data only" in output
    assert "Relevant services with insufficient data" in output
    assert message in output
    assert "No matching services" not in output
    distance = "unknown" if missing_field == "coordinates" else "not requested"
    assert f"Distance: {distance}" in output


@pytest.mark.parametrize("args", [["--service", "nonexistent"], ["--city", "Atlantis"]])
def test_cli_reports_no_matching_services_in_catalog(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*args, "--max-price", "50"]) == 0
    output = capsys.readouterr().out
    assert "No matching services in the loaded catalog" in output
    assert "insufficient data" not in output


def test_cli_shows_confirmed_and_uncertain_sections(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], offering: ServiceOffering
) -> None:
    uncertain = replace(
        offering,
        id="unknown",
        facility=replace(offering.facility, name="Fictional Missing Price Clinic"),
        price=None,
    )
    monkeypatch.setattr("medscout.__main__.offerings_from_catalog", lambda catalog: (uncertain, offering))
    assert main(["--max-price", "50"]) == 0
    output = capsys.readouterr().out
    assert output.index("Confirmed matches:") < output.index("Fictional Test Clinic")
    assert output.index("Fictional Test Clinic") < output.index("Relevant services with insufficient data")
    assert output.index("Relevant services with insufficient data") < output.index("Fictional Missing Price Clinic")
    assert "maximum price filter requires a recorded price" in output


@pytest.mark.parametrize(
    "args, message",
    [
        (["--radius-km", "30"], "radius requires origin"),
        (["--origin", "91", "0"], "latitude"),
        (["--max-price", "invalid"], "expected a decimal number"),
    ],
)
def test_cli_invalid_arguments(
    args: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert message in capsys.readouterr().err
