"""ECB euro reference rates: table, parsers and EUR conversion (plan §10, D11)."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from xml.etree import ElementTree

from .models import Money

# Currencies that joined the euro; ECB no longer publishes them (fixed conversion).
FIXED_EURO_RATES: dict[str, Decimal] = {
    "BGN": Decimal("1.95583"),
    "HRK": Decimal("7.53450"),
    "LTL": Decimal("3.45280"),
    "LVL": Decimal("0.702804"),
    "EEK": Decimal("15.6466"),
    "SKK": Decimal("30.1260"),
    "SIT": Decimal("239.640"),
    "CYP": Decimal("0.585274"),
    "MTL": Decimal("0.429300"),
}
MAX_LOOKBACK_DAYS = 10
_CENTS = Decimal("0.01")
_NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}

type RateTable = dict[date, dict[str, Decimal]]


@dataclass(frozen=True)
class FxConversion:
    eur_amount: Decimal
    rate: Decimal
    rate_date: date


class FxRateTable:
    """Rates per date: EUR 1 = rate × currency."""

    def __init__(self) -> None:
        self._rates: RateTable = {}

    def __len__(self) -> int:
        return len(self._rates)

    def add(self, day: date, rates: Mapping[str, Decimal]) -> None:
        self._rates.setdefault(day, {}).update(rates)

    def update(self, table: Mapping[date, Mapping[str, Decimal]]) -> int:
        """Merge rates; return how many dates were new."""
        new_dates = 0
        for day, rates in table.items():
            if day not in self._rates:
                new_dates += 1
            self.add(day, rates)
        return new_dates

    @property
    def dates(self) -> list[date]:
        return sorted(self._rates)

    def latest_date(self) -> date | None:
        return max(self._rates) if self._rates else None

    def currencies(self) -> set[str]:
        return {c for rates in self._rates.values() for c in rates}

    def rate_for(self, currency: str, on: date) -> tuple[Decimal, date] | None:
        """Rate on the date, else the latest earlier date within the lookback."""
        code = currency.upper()
        if code == "EUR":
            return Decimal(1), on
        if code in FIXED_EURO_RATES:
            return FIXED_EURO_RATES[code], on
        for back in range(MAX_LOOKBACK_DAYS + 1):
            day = on - timedelta(days=back)
            rates = self._rates.get(day)
            if rates and code in rates:
                return rates[code], day
        return None

    def convert_to_eur(self, money: Money, on: date) -> FxConversion | None:
        found = self.rate_for(money.currency, on)
        if found is None:
            return None
        rate, day = found
        eur = (money.amount / rate).quantize(_CENTS, ROUND_HALF_UP)
        return FxConversion(eur, rate, day)

    def prune_before(self, cutoff: date) -> int:
        old = [day for day in self._rates if day < cutoff]
        for day in old:
            del self._rates[day]
        return len(old)

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {
            day.isoformat(): {c: str(r) for c, r in sorted(rates.items())}
            for day, rates in sorted(self._rates.items())
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Mapping[str, str]]) -> FxRateTable:
        table = cls()
        for day, rates in data.items():
            parsed = {c: Decimal(r) for c, r in rates.items()}
            table.add(date.fromisoformat(day), parsed)
        return table


def _decimal(value: str | None) -> Decimal | None:
    if value is None or value.strip() in {"", "N/A"}:
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def parse_ecb_xml(text: str) -> RateTable:
    """Parse the daily or 90-day ECB XML.

    The stdlib parser is used deliberately to keep the integration free of
    third-party requirements: the feed is fetched from the ECB over HTTPS only,
    and the bundled expat rejects entity-expansion attacks (billion laughs)
    while ElementTree never resolves external entities.
    """
    root = ElementTree.fromstring(text)
    result: RateTable = {}
    for day_cube in root.iterfind(".//e:Cube[@time]", _NS):
        day = date.fromisoformat(day_cube.attrib["time"])
        rates: dict[str, Decimal] = {}
        for cube in day_cube.iterfind("e:Cube[@currency]", _NS):
            rate = _decimal(cube.attrib.get("rate"))
            if rate is not None:
                rates[cube.attrib["currency"].upper()] = rate
        if rates:
            result[day] = rates
    return result


def parse_ecb_history_csv(text: str) -> RateTable:
    """Parse eurofxref-hist.csv (``Date,USD,...`` with ``N/A`` gaps)."""
    result: RateTable = {}
    for row in csv.DictReader(io.StringIO(text)):
        raw_day = (row.get("Date") or "").strip()
        if not raw_day:
            continue
        rates: dict[str, Decimal] = {}
        for currency, value in row.items():
            if not currency or currency == "Date":
                continue
            rate = _decimal(value)
            if rate is not None:
                rates[currency.strip().upper()] = rate
        if rates:
            result[date.fromisoformat(raw_day)] = rates
    return result


def parse_ecb_history_zip(data: bytes) -> RateTable:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".csv"))
        return parse_ecb_history_csv(archive.read(name).decode("utf-8"))
