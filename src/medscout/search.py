"""Deterministic search over healthcare offerings supplied by a catalog adapter."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from math import asin, cos, isfinite, radians, sin, sqrt
from typing import Literal
from urllib.parse import quote

from .catalog import Facility


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


@dataclass(frozen=True, slots=True)
class Coordinates:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("latitude must be within [-90, 90] and longitude within [-180, 180]")


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    provenance: str
    verification_status: Literal["unverified", "verified"]
    url: str | None = None
    last_verified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FacilitySite:
    id: str
    name: str
    city: str
    region: str
    source: SourceMetadata
    province: str | None = None
    address: str | None = None
    coordinates: Coordinates | None = None


@dataclass(frozen=True, slots=True)
class Practitioner:
    id: str
    name: str
    source: SourceMetadata | None = None


@dataclass(frozen=True, slots=True)
class Price:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not self.amount.is_finite() or self.amount < 0:
            raise ValueError("price must be finite and non-negative")
        object.__setattr__(self, "currency", _currency_code(self.currency))


def _currency_code(value: str) -> str:
    code = value.strip().upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise ValueError("currency must be a three-letter code")
    return code


@dataclass(frozen=True, slots=True)
class WaitingTimeStatistic:
    days: int
    statistic: str
    measured_at: datetime | None = None
    source: SourceMetadata | None = None


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    rating: Decimal
    scale_max: Decimal
    review_count: int
    source: SourceMetadata | None = None


@dataclass(frozen=True, slots=True)
class BookingChannel:
    kind: str
    destination: str
    source: SourceMetadata | None = None


@dataclass(frozen=True, slots=True)
class BookableSlot:
    starts_at: datetime
    channel: BookingChannel | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ServiceOffering:
    id: str
    facility: FacilitySite
    service_name: str
    pathway: Literal["ssn", "private"] | None = None
    practitioners: tuple[Practitioner, ...] | None = None
    price: Price | None = None
    waiting_time: WaitingTimeStatistic | None = None
    reviews: ReviewSummary | None = None
    booking_channels: tuple[BookingChannel, ...] | None = None
    bookable_slots: tuple[BookableSlot, ...] | None = None
    source: SourceMetadata | None = None


@dataclass(frozen=True, slots=True)
class SearchQuery:
    service_name: str | None = None
    city: str | None = None
    province: str | None = None
    max_price: Decimal | None = None
    currency: str = "EUR"
    origin: Coordinates | None = None
    radius_km: float | None = None

    def __post_init__(self) -> None:
        if self.max_price is not None:
            price = Price(self.max_price, self.currency)
            object.__setattr__(self, "currency", price.currency)
        if self.radius_km is not None:
            if self.origin is None:
                raise ValueError("radius requires origin coordinates")
            if not isfinite(self.radius_km) or self.radius_km < 0:
                raise ValueError("radius must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SearchResult:
    offering: ServiceOffering
    distance_km: float | None


type MissingFilterData = Literal["province", "price", "coordinates"]


@dataclass(frozen=True, slots=True)
class UncertainCandidate(SearchResult):
    missing_data: tuple[MissingFilterData, ...]


@dataclass(frozen=True, slots=True)
class SearchResponse:
    matches: tuple[SearchResult, ...]
    uncertain_candidates: tuple[UncertainCandidate, ...]


def offerings_from_catalog(facilities: Iterable[Facility]) -> tuple[ServiceOffering, ...]:
    """Adapt legacy synthetic records without adding claims about their services."""
    offerings: list[ServiceOffering] = []
    for record in facilities:
        facility = FacilitySite(
            id=record.id,
            name=record.name,
            city=record.city,
            region=record.region,
            source=SourceMetadata(record.provenance, record.verification_status),
        )
        seen_services: set[str] = set()
        for service in record.services:
            service_key = _normalize(service)
            if service_key in seen_services:
                continue
            seen_services.add(service_key)
            offering_id = f"{quote(facility.id, safe='')}:{quote(service_key, safe='')}"
            offerings.append(
                ServiceOffering(offering_id, facility, service)
            )
    return tuple(offerings)


def haversine_km(origin: Coordinates, destination: Coordinates) -> float:
    """Return great-circle distance using the mean Earth radius in kilometers."""
    lat1, lat2 = radians(origin.latitude), radians(destination.latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(destination.longitude - origin.longitude)
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(min(1.0, max(0.0, a))))


def _result_key(result: SearchResult) -> tuple[float, str, str, str, str, str]:
    offering = result.offering
    facility = offering.facility
    distance = result.distance_km if result.distance_km is not None else float("inf")
    return (
        distance,
        _normalize(facility.city),
        _normalize(facility.name),
        _normalize(offering.service_name),
        facility.id,
        offering.id,
    )


def search_offerings_with_details(
    offerings: Iterable[ServiceOffering], query: SearchQuery
) -> SearchResponse:
    """Report confirmed matches and candidates with only missing filter data."""
    service = _normalize(query.service_name or "")
    city = _normalize(query.city or "")
    province = _normalize(query.province or "")
    matches: list[SearchResult] = []
    uncertain: list[UncertainCandidate] = []

    for offering in offerings:
        facility = offering.facility
        if service and service not in _normalize(offering.service_name):
            continue
        if city and city != _normalize(facility.city):
            continue

        missing: list[MissingFilterData] = []
        if province:
            candidate_province = _normalize(facility.province or "")
            if not candidate_province:
                missing.append("province")
            elif candidate_province != province:
                continue
        if query.max_price is not None:
            price = offering.price
            if price is None:
                missing.append("price")
            elif price.currency != query.currency or price.amount > query.max_price:
                continue

        distance = None
        if query.origin is not None and facility.coordinates is not None:
            distance = haversine_km(query.origin, facility.coordinates)
        if query.radius_km is not None:
            if distance is None:
                missing.append("coordinates")
            elif distance > query.radius_km:
                continue

        if missing:
            uncertain.append(UncertainCandidate(offering, distance, tuple(missing)))
        else:
            matches.append(SearchResult(offering, distance))

    return SearchResponse(
        matches=tuple(sorted(matches, key=_result_key)),
        uncertain_candidates=tuple(sorted(uncertain, key=_result_key)),
    )


def search_offerings(
    offerings: Iterable[ServiceOffering], query: SearchQuery
) -> tuple[SearchResult, ...]:
    """Return only confirmed matches, preserving the original search interface."""
    return search_offerings_with_details(offerings, query).matches
