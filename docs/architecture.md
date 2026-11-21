# Architecture

MedScout uses a src layout and the Python standard library at runtime. Project metadata, package data, and pytest settings live in pyproject.toml.

## Catalog and search models

`medscout.load_catalog()` reads the legacy synthetic JSON through `importlib.resources`. It also accepts a local path following the same schema. It validates required fields, values, and unique facility IDs. Invalid data raises `ValueError`. File access errors propagate to the caller.

`medscout.search` separates facility sites, service offerings, and practitioners. A facility carries location and source metadata. Each offering represents a service at that site and can carry its own source, SSN or private pathway, practitioners, price, waiting-time statistic, review summary, booking channels, and bookable slots. A booking channel or waiting-time statistic alone provides no evidence of a slot. Source metadata can carry a URL and last verification timestamp. Optional values remain unknown when absent. In particular an absent price differs from a recorded zero and absent slots differ from a source explicitly reporting an empty collection.

`offerings_from_catalog()` adapts legacy records without changing their facility IDs, provenance, or verification status. The adapter derives offering IDs from the facility ID and normalized service name. Future adapters should supply unique, stable offering IDs from source identifiers or a persisted mapping. They should normalize source data into the typed model and preserve source verification metadata at the level where it applies. The search function accepts any iterable of offerings and has no dependency on a database or a particular source.

## Search behavior

The search combines filters using AND. Service uses substring matching and city and province use full-name matching after Unicode case folding and whitespace normalization. An inclusive price cap uses decimal arithmetic and compares only values in the requested currency. An inclusive radius requires an origin and known facility coordinates. Haversine gives straight-line distance in kilometers. With an origin, known distances sort first. Ties sort by normalized city, facility name and service name, then by stable IDs.

`search_offerings_with_details()` returns a typed `SearchResponse` with confirmed matches and uncertain candidates. Each uncertain candidate carries the missing fields for its requested filters. A known mismatch in any filter takes precedence and excludes the offering from both groups. Both groups use the same ordering. `search_offerings()` remains available for callers that only need the original tuple of confirmed matches.

The CLI adapts the bundled catalog and labels its output as synthetic and unverified. It shows the two result groups separately and reports no matching services in the loaded catalog when both groups are empty.
