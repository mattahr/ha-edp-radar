import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from custom_components.edp_radar.fx_rates import (
    FIXED_EURO_RATES,
    FxConversion,
    FxRateTable,
    parse_ecb_history_csv,
    parse_ecb_history_zip,
    parse_ecb_xml,
)
from custom_components.edp_radar.models import Money

ECB = Path(__file__).parent / "fixtures" / "ecb"


def _table() -> FxRateTable:
    table = FxRateTable()
    table.add(date(2026, 9, 11), {"SEK": Decimal("11.2373"), "PLN": Decimal("4.3250")})
    table.add(date(2026, 9, 10), {"SEK": Decimal("11.1995"), "PLN": Decimal("4.3220")})
    return table


def test_parse_daily_xml() -> None:
    rates = parse_ecb_xml((ECB / "daily.xml").read_text())
    assert rates == {
        date(2026, 9, 11): {
            "USD": Decimal("1.1592"),
            "CZK": Decimal("24.264"),
            "DKK": Decimal("7.4748"),
            "PLN": Decimal("4.3250"),
            "SEK": Decimal("11.2373"),
            "NOK": Decimal("10.7805"),
        }
    }


def test_parse_90d_xml_has_two_dates() -> None:
    rates = parse_ecb_xml((ECB / "hist-90d.xml").read_text())
    assert sorted(rates) == [date(2026, 9, 10), date(2026, 9, 11)]
    assert rates[date(2026, 9, 10)]["PLN"] == Decimal("4.322")


def test_parse_history_csv_skips_na_and_trailing_comma() -> None:
    rates = parse_ecb_history_csv((ECB / "hist.csv").read_text())
    assert len(rates) == 3
    assert rates[date(2026, 9, 8)] == {
        "USD": Decimal("1.1601"),
        "PLN": Decimal("4.318"),
        "SEK": Decimal("11.1500"),
    }


def test_parse_history_zip() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("eurofxref-hist.csv", (ECB / "hist.csv").read_text())
    assert len(parse_ecb_history_zip(buffer.getvalue())) == 3


def test_eur_passthrough() -> None:
    conversion = _table().convert_to_eur(
        Money(Decimal("100.5"), "EUR"), date(2026, 9, 11)
    )
    assert conversion == FxConversion(Decimal("100.50"), Decimal(1), date(2026, 9, 11))


def test_sek_and_pln_conversion_on_exact_date() -> None:
    table = _table()
    sek = table.convert_to_eur(Money(Decimal("6000000"), "SEK"), date(2026, 9, 11))
    assert sek is not None
    assert sek.eur_amount == Decimal("533936.09")
    assert sek.rate == Decimal("11.2373")
    assert sek.rate_date == date(2026, 9, 11)
    pln = table.convert_to_eur(Money(Decimal("10306545.8"), "PLN"), date(2026, 9, 10))
    assert pln is not None
    assert pln.eur_amount == Decimal("2384670.48")


def test_weekend_falls_back_to_latest_previous_rate() -> None:
    sunday = date(2026, 9, 13)
    conversion = _table().convert_to_eur(Money(Decimal("100"), "SEK"), sunday)
    assert conversion is not None
    assert conversion.rate_date == date(2026, 9, 11)


def test_never_uses_a_later_rate_and_gives_up_after_lookback() -> None:
    table = _table()
    assert table.rate_for("SEK", date(2026, 9, 9)) is None  # only later dates known
    assert table.rate_for("SEK", date(2026, 10, 30)) is None  # > 10 days after latest


def test_missing_currency_is_none() -> None:
    money = Money(Decimal("1"), "XYZ")
    assert _table().convert_to_eur(money, date(2026, 9, 11)) is None


def test_fixed_euro_rates() -> None:
    conversion = FxRateTable().convert_to_eur(
        Money(Decimal("195.583"), "BGN"), date(2026, 1, 5)
    )
    assert conversion is not None
    assert conversion.eur_amount == Decimal("100.00")
    assert FIXED_EURO_RATES["HRK"] == Decimal("7.53450")


def test_update_prune_and_round_trip() -> None:
    table = _table()
    added = table.update(
        {
            date(2026, 9, 11): {"SEK": Decimal("11.2373")},
            date(2026, 9, 9): {"SEK": Decimal("11.1")},
        }
    )
    assert added == 1
    assert table.latest_date() == date(2026, 9, 11)
    assert table.currencies() == {"SEK", "PLN"}
    assert table.prune_before(date(2026, 9, 10)) == 1
    assert table.dates == [date(2026, 9, 10), date(2026, 9, 11)]
    data = table.to_dict()
    assert data["2026-09-11"]["SEK"] == "11.2373"
    assert FxRateTable.from_dict(data).to_dict() == data
    assert len(table) == 2
