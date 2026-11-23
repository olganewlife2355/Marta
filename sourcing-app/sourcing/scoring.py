"""Deterministic scoring parts: tenure, hunt window, donor matching, final score."""

import re
from datetime import date
from typing import Iterable, Optional

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "січ": 1, "лют": 2, "бер": 3, "кві": 4, "тра": 5, "чер": 6,
    "лип": 7, "сер": 8, "вер": 9, "жов": 10, "лис": 11, "гру": 12,
}

COMPANY_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "gmbh", "corp", "corporation", "co",
    "group", "holding", "holdings", "plc", "sa", "bv", "ou", "tov", "тов",
}

DONOR_TIER_POINTS = {1: 100, 2: 70, 3: 40}

DEFAULT_WEIGHTS = {"must_have": 35, "nice_to_have": 10, "donor": 25, "domain": 15, "seniority": 15}


def parse_start_date(value: str) -> Optional[date]:
    """Parse '2023-05', '2023-05-14', '05/2023', 'May 2023', '2023'."""
    if not value:
        return None
    s = str(value).strip().lower()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    m = re.fullmatch(r"(\d{1,2})[./](\d{4})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    m = re.fullmatch(r"([a-zа-яіїє]{3})[a-zа-яіїє]*\.?\s+(\d{4})", s)
    if m and m.group(1) in MONTHS:
        return date(int(m.group(2)), MONTHS[m.group(1)], 1)
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def parse_tenure_text(value: str) -> Optional[int]:
    """Parse LinkedIn-style durations: '2 yrs 3 mos', '1 year', '8 months', '2 р 3 міс'."""
    if not value:
        return None
    s = str(value).strip().lower()
    if re.fullmatch(r"\d+", s):
        return int(s)
    years = re.search(r"(\d+)\s*(?:yrs?|years?|р\.?|рок|роки|років)", s)
    months = re.search(r"(\d+)\s*(?:mos?|months?|міс)", s)
    if not years and not months:
        return None
    return (int(years.group(1)) * 12 if years else 0) + (int(months.group(1)) if months else 0)


def tenure_months(start_value: str = "", tenure_value: str = "", today: Optional[date] = None) -> Optional[int]:
    today = today or date.today()
    start = parse_start_date(start_value)
    if start:
        return max(0, (today.year - start.year) * 12 + today.month - start.month)
    return parse_tenure_text(tenure_value)


def hunt_window(months: Optional[int]) -> tuple[str, str]:
    """Return (badge, explanation) for how huntable a candidate is by tenure."""
    if months is None:
        return "⚪", "Немає даних про стаж у поточній компанії"
    if months < 12:
        return "🔴", f"{months} міс. у компанії: рано хантити"
    if months <= 36:
        return "🟢", f"{months} міс. у компанії: оптимальне вікно для хантингу"
    return "🟡", f"{months} міс. у компанії: довго на місці, перевірити стагнацію"


def normalize_company(name: str) -> str:
    s = re.sub(r"[^\w\s]", " ", str(name or "").lower())
    words = [w for w in s.split() if w not in COMPANY_SUFFIXES]
    return " ".join(words)


def match_donor(company: str, donors: Iterable[dict]) -> Optional[dict]:
    """Find the donor (dict with name/tier) matching the company, best tier first."""
    norm = normalize_company(company)
    if not norm:
        return None
    hits = []
    for d in donors:
        dn = normalize_company(d.get("name", ""))
        if not dn:
            continue
        if dn == norm or (len(dn) >= 4 and re.search(rf"\b{re.escape(dn)}\b", norm)):
            hits.append(d)
    return min(hits, key=lambda d: int(d.get("tier", 3))) if hits else None


def donor_points(current_donor: Optional[dict], past_donor_tiers: Iterable[int] = ()) -> int:
    """Current donor company counts fully, past donor experience counts at half."""
    pts = DONOR_TIER_POINTS.get(int(current_donor["tier"]), 0) if current_donor else 0
    past = [DONOR_TIER_POINTS.get(int(t), 0) // 2 for t in past_donor_tiers]
    return max([pts, *past])


def weighted_criteria_score(scores: list[dict], criteria: list[dict]) -> Optional[float]:
    """0-100 score from per-criterion 0-10 scores, weighted by criterion weight."""
    weights = {c["name"].strip().lower(): max(1, int(c.get("weight", 1))) for c in criteria}
    total = norm = 0.0
    for s in scores:
        w = weights.get(s["criterion"].strip().lower(), 1)
        total += w * min(10, max(0, int(s["score"]))) * 10
        norm += w
    return total / norm if norm else None


def final_score(parts: dict, weights: Optional[dict] = None) -> int:
    """Combine 0-100 parts by weights; parts that are None are skipped and weights re-normalized."""
    weights = weights or DEFAULT_WEIGHTS
    total = norm = 0.0
    for key, w in weights.items():
        v = parts.get(key)
        if v is None or w <= 0:
            continue
        total += w * v
        norm += w
    return round(total / norm) if norm else 0
