"""Frozen, Home-Assistant-independent spending models (S4, S5).

Every datapoint carries its own provenance: source, metric, country, reference
period, unit, status, release and publication date (plan §6). Retrieval time
lives on the ``SourceSeries`` because a whole release is retrieved at once.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

type DatapointKey = tuple[str, str, str, str, str, str]

_MONTH_ABBREVIATIONS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


class DatapointStatus(StrEnum):
    """Controlled vocabulary of plan §8."""

    ACTUAL = "actual"
    PRELIMINARY = "preliminary"
    PROVISIONAL = "provisional"
    ESTIMATE = "estimate"
    PROJECTION = "projection"
    BUDGET = "budget"


class Cadence(StrEnum):
    MONTHLY = "monthly"
    TWICE_YEARLY = "twice_yearly"
    ANNUAL = "annual"


class ProviderState(StrEnum):
    """Per-provider health (plan §64)."""

    NEVER_LOADED = "never_loaded"
    AVAILABLE = "available"
    STALE_BUT_CACHED = "stale_but_cached"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    PARSER_ERROR = "parser_error"
    SCHEMA_CHANGED = "schema_changed"


def _opt_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _opt_datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def month_abbreviation(month: int) -> str:
    """Three-letter English abbreviation of ``month`` (1-12), e.g. ``"Jan"``."""
    return _MONTH_ABBREVIATIONS[month - 1]


@dataclass(frozen=True, slots=True)
class ReferencePeriod:
    """The period a value describes; ``label`` is for display only."""

    start: date
    end: date
    label: str

    @classmethod
    def year(cls, year: int) -> ReferencePeriod:
        return cls(date(year, 1, 1), date(year, 12, 31), str(year))

    @classmethod
    def month(cls, year: int, month: int) -> ReferencePeriod:
        last_day = calendar.monthrange(year, month)[1]
        return cls(
            date(year, month, 1),
            date(year, month, last_day),
            f"{month_abbreviation(month)} {year}",
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferencePeriod:
        return cls(
            date.fromisoformat(data["start"]),
            date.fromisoformat(data["end"]),
            str(data["label"]),
        )


@dataclass(frozen=True, slots=True)
class SourceRelease:
    """One discovered publication of a source (plan §10, §67)."""

    source_id: str
    release_id: str
    published_at: date | None
    download_url: str
    canonical_url: str
    format: str
    etag: str | None = None
    last_modified: str | None = None
    checksum: str | None = None
    layout_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "release_id": self.release_id,
            "published_at": None
            if self.published_at is None
            else self.published_at.isoformat(),
            "download_url": self.download_url,
            "canonical_url": self.canonical_url,
            "format": self.format,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "checksum": self.checksum,
            "layout_fingerprint": self.layout_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRelease:
        return cls(
            source_id=str(data["source_id"]),
            release_id=str(data["release_id"]),
            published_at=_opt_date(data.get("published_at")),
            download_url=str(data["download_url"]),
            canonical_url=str(data["canonical_url"]),
            format=str(data["format"]),
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            checksum=data.get("checksum"),
            layout_fingerprint=data.get("layout_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class SpendingDataPoint:
    """One value with full provenance (plan §6). ``flags`` keeps source markers."""

    source_id: str
    metric_id: str
    country: str
    reference: ReferencePeriod
    value: Decimal
    unit: str
    status: DatapointStatus
    release_id: str
    published_at: date | None
    source_url: str
    flags: tuple[str, ...] = ()

    @property
    def key(self) -> DatapointKey:
        """Logical identity (S5)."""
        return (
            self.source_id,
            self.metric_id,
            self.country,
            self.reference.start.isoformat(),
            self.reference.end.isoformat(),
            self.unit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "metric_id": self.metric_id,
            "country": self.country,
            "reference": self.reference.to_dict(),
            "value": str(self.value),
            "unit": self.unit,
            "status": self.status.value,
            "release_id": self.release_id,
            "published_at": None
            if self.published_at is None
            else self.published_at.isoformat(),
            "source_url": self.source_url,
            "flags": list(self.flags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpendingDataPoint:
        return cls(
            source_id=str(data["source_id"]),
            metric_id=str(data["metric_id"]),
            country=str(data["country"]),
            reference=ReferencePeriod.from_dict(data["reference"]),
            value=Decimal(str(data["value"])),
            unit=str(data["unit"]),
            status=DatapointStatus(data["status"]),
            release_id=str(data["release_id"]),
            published_at=_opt_date(data.get("published_at")),
            source_url=str(data["source_url"]),
            flags=tuple(str(flag) for flag in data.get("flags", [])),
        )


@dataclass(frozen=True, slots=True)
class Revision:
    """A changed value on an existing key (plan §62)."""

    key: DatapointKey
    previous_value: Decimal
    previous_release_id: str
    new_value: Decimal
    release_id: str
    detected_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": list(self.key),
            "previous_value": str(self.previous_value),
            "previous_release_id": self.previous_release_id,
            "new_value": str(self.new_value),
            "release_id": self.release_id,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Revision:
        key = tuple(str(part) for part in data["key"])
        if len(key) != 6:
            raise ValueError(f"datapoint key must have 6 parts, got {key!r}")
        return cls(
            key=(key[0], key[1], key[2], key[3], key[4], key[5]),
            previous_value=Decimal(str(data["previous_value"])),
            previous_release_id=str(data["previous_release_id"]),
            new_value=Decimal(str(data["new_value"])),
            release_id=str(data["release_id"]),
            detected_at=datetime.fromisoformat(data["detected_at"]),
        )


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Per-provider state exposed by diagnostics (plan §64, §80)."""

    state: ProviderState = ProviderState.NEVER_LOADED
    last_check_at: datetime | None = None
    next_check_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    warnings: tuple[str, ...] = ()
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "last_check_at": _iso(self.last_check_at),
            "next_check_at": _iso(self.next_check_at),
            "last_success_at": _iso(self.last_success_at),
            "last_error": self.last_error,
            "warnings": list(self.warnings),
            "skip_reason": self.skip_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderHealth:
        return cls(
            state=ProviderState(data.get("state", ProviderState.NEVER_LOADED.value)),
            last_check_at=_opt_datetime(data.get("last_check_at")),
            next_check_at=_opt_datetime(data.get("next_check_at")),
            last_success_at=_opt_datetime(data.get("last_success_at")),
            last_error=data.get("last_error"),
            warnings=tuple(str(w) for w in data.get("warnings", [])),
            skip_reason=data.get("skip_reason"),
        )


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


@dataclass(frozen=True, slots=True)
class SourceSeries:
    """Everything stored for one source: current release, health, all datapoints."""

    source_id: str
    release: SourceRelease | None
    health: ProviderHealth
    datapoints: tuple[SpendingDataPoint, ...]
    revisions: tuple[Revision, ...]
    retrieved_at: datetime | None

    @classmethod
    def empty(cls, source_id: str) -> SourceSeries:
        return cls(source_id, None, ProviderHealth(), (), (), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "release": None if self.release is None else self.release.to_dict(),
            "health": self.health.to_dict(),
            "datapoints": [point.to_dict() for point in self.datapoints],
            "revisions": [revision.to_dict() for revision in self.revisions],
            "retrieved_at": _iso(self.retrieved_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceSeries:
        release = data.get("release")
        return cls(
            source_id=str(data["source_id"]),
            release=None if release is None else SourceRelease.from_dict(release),
            health=ProviderHealth.from_dict(data.get("health", {})),
            datapoints=tuple(
                SpendingDataPoint.from_dict(item) for item in data.get("datapoints", [])
            ),
            revisions=tuple(
                Revision.from_dict(item) for item in data.get("revisions", [])
            ),
            retrieved_at=_opt_datetime(data.get("retrieved_at")),
        )


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """Definition of one metric of one source (plan §47)."""

    metric_id: str
    source_id: str
    display_name: str
    definition: str
    unit: str
    comparison_group: str


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Source registry entry (plan §9, §57, §86)."""

    source_id: str
    display_name: str
    publisher: str
    official: bool
    canonical_url: str
    cadence: Cadence
    expected_lag_days: int
    check_interval: timedelta
    formats: tuple[str, ...] = field(default_factory=tuple)
