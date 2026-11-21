# MedScout

MedScout is a project for discovering and comparing healthcare services. The current command-line search uses a fictional, unverified facilities catalog for Emilia-Romagna.

## Windows setup

Open PowerShell in the repository root. Use the existing Python 3.15 virtual environment or create one with `py -3.15 -m venv .venv`.

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider
```

If pytest or the package is missing, install them using `.\.venv\Scripts\python.exe -m pip install -e ".[test]"`. The editable install makes the CLI available from the repository root. The application and tests do not make network requests.

## Search

```powershell
.\.venv\Scripts\python.exe -B -m medscout --help
.\.venv\Scripts\python.exe -B -m medscout --service "dermatology" --city "Bologna"
.\.venv\Scripts\python.exe -B -m medscout --origin 44.4949 11.3426 --radius-km 30
```

Service names support substring matching. City and province match full names. Searches ignore case and normalize whitespace. An origin orders results by straight-line distance when coordinates are available. Add `--radius-km` to require a known distance within the limit. `--max-price` requires a recorded price in `--currency`, which defaults to EUR.

The bundled synthetic catalog has no recorded facility coordinates, provinces, or prices. When a relevant service lacks the data needed for a requested filter, the CLI lists it separately under insufficient data and names the filter it could not evaluate. A known filter mismatch excludes the service even if another field is missing. If both result groups are empty, the CLI reports no matching services in the loaded catalog. Distance is marked as not requested when no origin is supplied. Its facilities and services are fictional and unverified and cannot be used for booking.

## Documentation

- [Product scope](docs/product.md)
- [Architecture](docs/architecture.md)
- [Current status](docs/current-status.md)
