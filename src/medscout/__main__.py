"""Command-line search for the bundled synthetic catalog."""

import argparse
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from .catalog import load_catalog
from .search import (
    Coordinates,
    MissingFilterData,
    SearchQuery,
    SearchResult,
    offerings_from_catalog,
    search_offerings_with_details,
)


_MISSING_FILTER_MESSAGES: dict[MissingFilterData, str] = {
    "province": "province filter requires a recorded province",
    "price": "maximum price filter requires a recorded price",
    "coordinates": "radius filter requires facility coordinates",
}


def _print_result(result: SearchResult, origin_requested: bool) -> None:
    offering = result.offering
    facility = offering.facility
    price = "unknown"
    if offering.price is not None:
        price = f"{offering.price.amount} {offering.price.currency}"
    distance = "not requested"
    if origin_requested:
        distance = "unknown" if result.distance_km is None else f"{result.distance_km:.1f} km"
    print(f"- {offering.service_name} | {facility.name} | {facility.city} | {facility.id}")
    print(
        f"  Price: {price} | Distance: {distance} | "
        f"{facility.source.provenance}, {facility.source.verification_status}"
    )


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("expected a decimal number") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the MedScout synthetic healthcare catalog.")
    parser.add_argument("--service", help="Service name or substring")
    parser.add_argument("--city", help="City name")
    parser.add_argument("--province", help="Province name")
    parser.add_argument("--max-price", type=_decimal, help="Maximum known price, inclusive")
    parser.add_argument("--currency", default="EUR", help="Currency for --max-price (default: EUR)")
    parser.add_argument("--origin", nargs=2, type=float, metavar=("LAT", "LON"), help="Origin in decimal degrees")
    parser.add_argument("--radius-km", type=float, metavar="KM", help="Maximum distance, requires --origin")
    args = parser.parse_args(argv)
    try:
        query = SearchQuery(
            service_name=args.service,
            city=args.city,
            province=args.province,
            max_price=args.max_price,
            currency=args.currency,
            origin=Coordinates(*args.origin) if args.origin is not None else None,
            radius_km=args.radius_km,
        )
    except ValueError as error:
        parser.error(str(error))

    print("Synthetic data only. Facilities and services are fictional and unverified.")
    print("Results cannot be used to book appointments.")
    response = search_offerings_with_details(offerings_from_catalog(load_catalog()), query)
    if not response.matches and not response.uncertain_candidates:
        print("No matching services in the loaded catalog.")
        return 0

    origin_requested = query.origin is not None
    if response.matches:
        print("Confirmed matches:")
        for result in response.matches:
            _print_result(result, origin_requested)

    if response.uncertain_candidates:
        print("Relevant services with insufficient data to confirm eligibility:")
        for candidate in response.uncertain_candidates:
            _print_result(candidate, origin_requested)
            reasons = "; ".join(_MISSING_FILTER_MESSAGES[reason] for reason in candidate.missing_data)
            print(f"  Could not evaluate: {reasons}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
