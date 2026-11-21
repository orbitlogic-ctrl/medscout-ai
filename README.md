# MedScout

MedScout is a project for discovering and comparing healthcare services. Milestone 1 provides a fictional facilities catalog for Emilia-Romagna and a typed Python loader.

## Windows setup

Open PowerShell in the repository root. Use the existing Python 3.15 virtual environment:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider
```

For a fresh checkout, create the environment with `py -3.15 -m venv .venv`. Install the package and test dependencies with `.\.venv\Scripts\python.exe -m pip install -e ".[test]"` if pytest is missing or if you want to import the package outside pytest.

## Documentation

- [Product scope](docs/product.md)
- [Architecture](docs/architecture.md)
- [Current status](docs/current-status.md)
