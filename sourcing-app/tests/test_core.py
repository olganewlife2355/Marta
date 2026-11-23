from datetime import date
from unittest.mock import patch

import pytest

from sourcing import db, importer, service
from sourcing.scoring import (
    final_score,
    hunt_window,
    match_donor,
    parse_start_date,
    parse_tenure_text,
    tenure_months,
    weighted_criteria_score,
)

TODAY = date(2026, 11, 23)
DONORS = [
    {"name": "Headway", "tier": 1, "reason": ""},
    {"name": "BetterMe", "tier": 1, "reason": ""},
    {"name": "MacPaw", "tier": 2, "reason": ""},
    {"name": "Grammarly", "tier": 3, "reason": ""},
]


@pytest.mark.parametrize("value,expected", [
    ("2023-05", date(2023, 5, 1)),
    ("2023-05-14", date(2023, 5, 1)),
    ("05/2023", date(2023, 5, 1)),
    ("May 2023", date(2023, 5, 1)),
    ("травень 2023", date(2023, 5, 1)),
    ("2023", date(2023, 1, 1)),
    ("", None),
    ("present", None),
])
def test_parse_start_date(value, expected):
    assert parse_start_date(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("2 yrs 3 mos", 27), ("1 year", 12), ("8 months", 8), ("2 р 3 міс", 27), ("14", 14), ("n/a", None),
])
def test_parse_tenure_text(value, expected):
    assert parse_tenure_text(value) == expected


def test_tenure_prefers_start_date():
    assert tenure_months("2025-11", "5 years", today=TODAY) == 12


def test_hunt_window_bands():
    assert hunt_window(None)[0] == "⚪"
    assert hunt_window(11)[0] == "🔴"
    assert hunt_window(12)[0] == "🟢"
    assert hunt_window(36)[0] == "🟢"
    assert hunt_window(37)[0] == "🟡"


def test_match_donor():
    assert match_donor("Headway Inc.", DONORS)["name"] == "Headway"
    assert match_donor("MacPaw Way Ltd", DONORS)["name"] == "MacPaw"
    assert match_donor("Some Outsourcing LLC", DONORS) is None
    assert match_donor("", DONORS) is None


def test_weighted_and_final_score():
    crit = [{"name": "Swift", "weight": 3}, {"name": "Paywalls", "weight": 1}]
    scores = [{"criterion": "Swift", "score": 10}, {"criterion": "paywalls", "score": 2}]
    assert weighted_criteria_score(scores, crit) == pytest.approx(80.0)
    # None parts are skipped and weights re-normalized
    assert final_score({"must_have": 80, "donor": None}, {"must_have": 35, "donor": 25}) == 80
    assert final_score({"must_have": 80, "donor": 100}, {"must_have": 50, "donor": 50}) == 90


def test_import_sample_csv():
    data = open("sample_data/candidates_sample.csv", "rb").read()
    df = importer.read_csv(data)
    mapping = importer.guess_mapping(list(df.columns))
    assert mapping["current_company"] == ["Company"]
    assert mapping["profile_text"] == ["Summary", "Experience"]
    rows = importer.rows_from_df(df, mapping, "sample")
    assert len(rows) == 3 and rows[0]["full_name"] == "Олена Приклад"
    assert "Experience: Headway" in rows[0]["profile_text"]


def test_pipeline_end_to_end_with_mocked_claude(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    scorecard = {
        "must_have": [{"name": "Swift", "description": "", "weight": 3}],
        "nice_to_have": [{"name": "Paywalls", "description": "", "weight": 1}],
        "donor_companies": DONORS,
    }
    vid = db.add_vacancy(conn, "Senior iOS", "jd", "kickoff")
    db.update_vacancy(conn, vid, scorecard=scorecard)
    cid = db.upsert_candidate(conn, {"full_name": "A", "linkedin_url": "https://x/in/a/", "current_company": "Some LLC"})
    assert db.upsert_candidate(conn, {"full_name": "A2", "linkedin_url": "https://x/in/a"}) == cid
    db.attach(conn, vid, cid)
    fake = {
        "must_have_scores": [{"criterion": "Swift", "score": 9, "evidence": "e"}],
        "nice_to_have_scores": [{"criterion": "Paywalls", "score": 5, "evidence": "e"}],
        "domain_fit": 8, "seniority_fit": 7,
        "donor_companies_in_history": ["Headway"],
        "red_flags_found": [], "summary": "s", "connection_note": "hi",
    }
    with patch("sourcing.ai.assess_candidate", return_value=fake):
        score = service.score_candidate(conn, db.get_vacancy(conn, vid), cid)
    # must 90*35 + nice 50*10 + donor (past T1 -> 50)*25 + domain 80*15 + seniority 70*15, / 100
    assert score == round((90 * 35 + 50 * 10 + 50 * 25 + 80 * 15 + 70 * 15) / 100)
    row = db.pipeline_rows(conn, vid)[0]
    assert row["assessment"]["parts"]["donor"] == 50
    assert row["full_name"] == "A2"
