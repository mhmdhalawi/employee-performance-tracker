import io

import pandas as pd
import pytest

from app.core.errors import (
    FileParseError,
    SchemaValidationError,
    UnsupportedFileTypeError,
)
from app.services.file_processor import process_file
from app.services.profiles import build_column_mapping, detect_profile, get_profile

SUPPORT_CSV = (
    "Employee ID,Name,Period,Tickets Resolved,Avg Response Time,CSAT,Attendance Rate\n"
    "E1,Alice,2026-07,120,15,0.92,0.99\n"
    "E2,Bob,2026-07,80,25,0.85,0.95\n"
)


def to_excel_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


class TestValidation:
    def test_rejects_unknown_extension(self):
        with pytest.raises(UnsupportedFileTypeError):
            process_file("data.txt", b"anything")

    def test_rejects_empty_file(self):
        with pytest.raises(FileParseError):
            process_file("data.csv", b"")

    def test_rejects_header_only_file(self):
        with pytest.raises(FileParseError):
            process_file("data.csv", b"Employee ID,Tickets Resolved\n")

    def test_rejects_file_without_identifier_column(self):
        content = b"Tickets Resolved,CSAT\n120,0.9\n"
        with pytest.raises(SchemaValidationError):
            process_file("data.csv", content)

    def test_rejects_file_with_no_recognizable_metrics(self):
        content = b"Employee ID,Favourite Colour\nE1,blue\n"
        with pytest.raises(SchemaValidationError):
            process_file("data.csv", content)


class TestProfileDetection:
    def test_detects_support_profile(self):
        headers = ["Employee ID", "Tickets Resolved", "CSAT"]
        profile, matched = detect_profile(headers)
        assert profile.key == "support"
        assert matched == 2

    def test_detects_developer_profile(self):
        headers = ["Employee ID", "Story Points", "Cycle Time", "Bugs"]
        profile, matched = detect_profile(headers)
        assert profile.key == "developer"
        assert matched == 3

    def test_explicit_profile_overrides_detection(self):
        processed = process_file("d.csv", SUPPORT_CSV.encode(), profile_key="developer")
        assert processed.profile.key == "developer"
        assert processed.profile_detected is False


class TestColumnMapping:
    def test_matches_messy_headers(self):
        profile = get_profile("support")
        mapping = build_column_mapping(
            ["Employee ID", "Avg. Response Time (minutes)", "CSAT Score"], profile
        )

        assert mapping.id_column == "Employee ID"
        assert mapping.metric_columns["avg_response_time_minutes"] == (
            "Avg. Response Time (minutes)"
        )
        assert mapping.metric_columns["customer_satisfaction"] == "CSAT Score"

    def test_collects_unrecognized_headers(self):
        profile = get_profile("support")
        mapping = build_column_mapping(["Employee ID", "Random Note"], profile)
        assert mapping.unmapped == ["Random Note"]


class TestNormalization:
    def test_reads_csv_into_records(self):
        processed = process_file("perf.csv", SUPPORT_CSV.encode())

        assert processed.profile.key == "support"
        assert processed.row_count == 2
        assert [r.employee_id for r in processed.records] == ["E1", "E2"]

        alice = processed.records[0]
        assert alice.employee_name == "Alice"
        assert alice.period == "2026-07"
        assert alice.metrics["tickets_resolved"] == 120.0
        assert alice.metrics["customer_satisfaction"] == 0.92

    def test_reads_excel_into_records(self):
        frame = pd.read_csv(io.StringIO(SUPPORT_CSV))
        processed = process_file("perf.xlsx", to_excel_bytes(frame))

        assert [r.employee_id for r in processed.records] == ["E1", "E2"]
        assert processed.records[0].metrics["tickets_resolved"] == 120.0

    def test_row_without_identifier_is_skipped_and_reported(self):
        content = (
            "Employee ID,Tickets Resolved\n" "E1,120\n" ",90\n"
        ).encode()
        processed = process_file("perf.csv", content)

        assert len(processed.records) == 1
        assert any(i.severity == "error" for i in processed.issues)

    def test_bad_cell_is_reported_and_metric_dropped(self):
        content = (
            "Employee ID,Tickets Resolved,CSAT\n" "E1,not-a-number,0.9\n"
        ).encode()
        processed = process_file("perf.csv", content)

        record = processed.records[0]
        assert "tickets_resolved" not in record.metrics  # not coerced to 0
        assert record.metrics["customer_satisfaction"] == 0.9
        assert any("not numeric" in i.message for i in processed.issues)

    def test_percent_and_separator_formats_are_parsed(self):
        content = (
            "Employee ID,Tickets Resolved,CSAT\n" 'E1,"1,200",92%\n'
        ).encode()
        processed = process_file("perf.csv", content)

        assert processed.records[0].metrics["tickets_resolved"] == 1200.0
        assert processed.records[0].metrics["customer_satisfaction"] == 0.92

    def test_raw_row_is_preserved_for_traceability(self):
        processed = process_file("perf.csv", SUPPORT_CSV.encode())
        assert processed.records[0].raw["Tickets Resolved"] == "120"
