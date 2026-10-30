"""Guardrails against invalid percentages and lost survey meaning."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.audit import eurostat_frame
from src.validation import validate_cached_evidence, validate_observations

ROOT = Path(__file__).resolve().parents[1]


def test_sparse_jsonstat_keeps_missing_and_flags(tmp_path):
    payload = {
        "id": ["geo", "sex"],
        "size": [2, 2],
        "dimension": {
            "geo": {"category": {"index": {"FR": 0, "DE": 1}}},
            "sex": {"category": {"index": ["T", "F"]}},
        },
        "value": {"0": 40.0, "1": 45.0},
        "status": {"2": "u"},
    }
    path = tmp_path / "sparse.json"
    path.write_text(json.dumps(payload))
    frame, _ = eurostat_frame(path)
    assert len(frame) == 4
    assert frame.loc[2, "geo"] == "DE"
    assert pd.isna(frame.loc[2, "value"])
    assert frame.loc[2, "status_flag"] == "u"


def test_published_evidence_reconciles():
    checks = validate_cached_evidence()
    assert checks["country_rates_reconciled"] == 32
    genres = pd.read_csv(ROOT / "data/processed/genre_profiles.csv")
    absent = genres[
        (genres.country_iso3 == "CAN")
        & (genres.format_label == "Audiobook")
        & (genres.genre == "Comics or Graphic Novels")
    ]
    assert len(absent) == 2
    assert absent.participation.isna().all()


@pytest.mark.parametrize("defect", ["out_of_range", "duplicate", "lost_denominator", "unknown_source"])
def test_curated_input_rejects_broken_meaning(defect):
    frame = pd.read_csv(ROOT / "data/curated/format_profiles.csv").iloc[:1].copy()
    sources = set(pd.read_csv(ROOT / "data/processed/source_register.csv").source_id)
    if defect == "out_of_range":
        frame.loc[frame.index[0], "participation"] = 101
    elif defect == "duplicate":
        frame = pd.concat([frame, frame])
    elif defect == "lost_denominator":
        frame.loc[frame.index[0], "denominator"] = None
    else:
        frame.loc[frame.index[0], "source_id"] = "unknown"
    with pytest.raises(ValueError):
        validate_observations(frame, sources)
