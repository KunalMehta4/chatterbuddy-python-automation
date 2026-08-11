"""Measure how many real place names the weather feature can resolve.

No city name is hard-coded in the application: ``weather <location>`` sends the
text to Open-Meteo's geocoding API, which is backed by the GeoNames database.
That makes coverage a claim about the integration rather than about a list, and
claims should be measured rather than assumed.

This script resolves every name in ``scripts/cities.txt`` and reports the hit
rate, so "works for hundreds of locations" is a number someone actually ran.

Usage:
    python scripts/verify_geocoding.py
    python scripts/verify_geocoding.py --limit 25          # quick check
    python scripts/verify_geocoding.py --delay 0.1         # gentler on the API
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatterbuddy.errors import NotFoundError, ServiceError  # noqa: E402
from chatterbuddy.services.http_client import HttpClient  # noqa: E402
from chatterbuddy.services.weather_service import WeatherService  # noqa: E402

DEFAULT_SAMPLE = Path(__file__).resolve().parent / "cities.txt"
CONSECUTIVE_ERROR_LIMIT = 5


def load_sample(path: Path) -> list[str]:
    """Read the sample file, dropping comments, blanks, and duplicates."""
    seen: set[str] = set()
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--limit", type=int, default=0, help="only check the first N names")
    parser.add_argument("--delay", type=float, default=0.05, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    if not args.sample.exists():
        print(f"Sample file not found: {args.sample}")
        return 2

    names = load_sample(args.sample)
    if args.limit:
        names = names[: args.limit]

    service = WeatherService(HttpClient(timeout=args.timeout))
    resolved: list[str] = []
    unresolved: list[str] = []
    failures: list[tuple[str, str]] = []
    consecutive_errors = 0

    print(f"Resolving {len(names)} unique place names via the Open-Meteo geocoding API...\n")

    for position, name in enumerate(names, start=1):
        try:
            location = service.geocode(name)
            resolved.append(name)
            consecutive_errors = 0
            if position % 50 == 0:
                print(f"  {position:>4}/{len(names)}  latest: {location.display_name}")
        except NotFoundError:
            unresolved.append(name)
            consecutive_errors = 0
        except ServiceError as error:
            # A transport failure says nothing about coverage, so it is counted
            # separately -- folding it into "unresolved" would understate the
            # result and make the report dishonest.
            failures.append((name, str(error)))
            consecutive_errors += 1
            if consecutive_errors >= CONSECUTIVE_ERROR_LIMIT:
                print(
                    f"\nStopping early: {CONSECUTIVE_ERROR_LIMIT} consecutive transport "
                    "failures. Check your network and run again."
                )
                break

        time.sleep(args.delay)

    attempted = len(resolved) + len(unresolved)
    rate = (len(resolved) / attempted * 100) if attempted else 0.0

    print("\n" + "=" * 60)
    print("GEOCODING COVERAGE")
    print("=" * 60)
    print(f"  Names in sample     {len(names)}")
    print(f"  Successfully looked up   {len(resolved)}")
    print(f"  Not found in the index   {len(unresolved)}")
    print(f"  Transport failures       {len(failures)} (excluded from the rate)")
    print(f"  Resolution rate     {rate:.1f}% of {attempted} attempted")

    if unresolved:
        preview = ", ".join(unresolved[:12])
        print(f"\n  Not found: {preview}{' ...' if len(unresolved) > 12 else ''}")
    if failures:
        print(f"\n  First transport failure: {failures[0][0]} -> {failures[0][1]}")

    print()
    return 0 if attempted and rate >= 95.0 else 1


if __name__ == "__main__":
    sys.exit(main())
