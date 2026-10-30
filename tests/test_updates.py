"""A check failure must not make old evidence look newly collected."""

from src.updates import checked_source


def test_failed_check_preserves_receipt_and_pending_review():
    previous = {"sha256": "old", "last_success_at": "2026-01-01", "review_pending": True}
    source = {
        "source_id": "pdf",
        "title": "Survey",
        "survey_year": 2024,
        "check_url": "https://example.org/report",
    }

    def fail(_):
        raise OSError("offline")

    row = checked_source(source, previous, fail)
    assert row["sha256"] == "old"
    assert row["last_success_at"] == "2026-01-01"
    assert row["latest_observation_year"] == 2024
    assert row["review_pending"] is True
    assert row["status"] == "Check failed; last reviewed data retained"


def test_changed_pdf_is_not_promoted_to_a_new_observation():
    source = {
        "source_id": "pdf",
        "title": "Survey",
        "survey_year": 2024,
        "check_url": "https://example.org/report",
    }
    row = checked_source(source, {"sha256": "old"}, lambda _: b"new report body")
    assert row["review_pending"] is True
    assert row["latest_observation_year"] == 2024
    assert row["status"] == "Changed source; extraction review needed"


def test_statcan_successful_http_error_page_preserves_validated_receipt():
    previous = {"sha256": "validated-table", "last_success_at": "2026-11-20", "review_pending": True}
    source = {
        "source_id": "statcan_ca_book_publishers",
        "title": "Canadian book publishers",
        "survey_year": 2024,
        "check_url": "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2110020001",
    }
    row = checked_source(source, previous, lambda _: b"<html>We're sorry! The website is currently unavailable.</html>")
    assert row["sha256"] == "validated-table"
    assert row["last_success_at"] == "2026-11-20"
    assert row["latest_observation_year"] == 2024
    assert row["review_pending"] is True
    assert row["status"] == "Check failed; last reviewed data retained"
    assert "instead of table data" in row["notes"]


def test_pending_review_survives_an_unchanged_subsequent_check():
    source = {
        "source_id": "pdf",
        "title": "Survey",
        "survey_year": 2024,
        "check_url": "https://example.org/report",
    }
    first = checked_source(source, {"sha256": "old"}, lambda _: b"new")
    second = checked_source(source, first, lambda _: b"new")
    assert second["review_pending"] is True
    assert second["status"] == "Changed source; extraction review needed"
