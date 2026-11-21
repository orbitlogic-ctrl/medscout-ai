# Current status

Milestone 1 provides Python project setup, the five-facility synthetic catalog, and a typed loader with validation.

Milestone 2A adds deterministic search by service, city, province, price, and straight-line radius. The typed model separates facilities, service offerings, and practitioners. It supports optional source metadata, SSN and private pathways, prices, waiting-time statistics, reviews, booking channels, and slots. The CLI uses the existing synthetic catalog. Its records lack province, coordinates, prices, and availability, so those values remain unknown.

Source adapters and real healthcare data remain future work.

The CLI reports confirmed matches separately from services whose eligibility cannot be evaluated. The compatibility search function still returns confirmed matches only.

Verified locally with Python 3.15.2 and pytest 9.2.0. All 59 offline tests passed, including missing-data reasons, known mismatches, mixed results, and CLI messaging.
