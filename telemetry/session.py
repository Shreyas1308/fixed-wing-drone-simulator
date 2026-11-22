"""Telemetry session management for one flight."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from telemetry.schema import TelemetryRecord
from telemetry.sinks.base import BaseSink


class TelemetrySession:
    """Groups telemetry from one flight and writes it to sinks."""

    def __init__(
        self,
        flight_id: str,
        sinks: Sequence[BaseSink],
    ) -> None:
        self.flight_id = flight_id
        self.sinks = list(sinks)
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.record_count = 0

    def start(self) -> None:
        self.started_at = datetime.now(timezone.utc)

        for sink in self.sinks:
            sink.open()

    def write(self, records: Sequence[TelemetryRecord]) -> None:
        for record in records:
            for sink in self.sinks:
                sink.write(record)

            self.record_count += 1

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc)

        for sink in self.sinks:
            sink.close()

        print(
            f"Session {self.flight_id} complete: "
            f"{self.record_count} records written."
        )