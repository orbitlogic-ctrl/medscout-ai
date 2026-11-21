# Architecture

The project uses a src layout. Project metadata, package data, and pytest settings live in pyproject.toml. The runtime uses the Python standard library.

The bundled JSON contains facility records with stable IDs, names, cities, regions, services, provenance, and verification status. Preserve an existing facility ID when editing its record.

`medscout.load_catalog()` reads the bundled JSON through `importlib.resources`. Pass a local `pathlib.Path` to load another file. The loader checks required fields, field values, and ID uniqueness before returning a tuple of immutable `Facility` instances. Invalid data raises `ValueError`. File access errors propagate to the caller.
