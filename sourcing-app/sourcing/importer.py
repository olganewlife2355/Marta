"""CSV import with column auto-mapping (Juicebox, LinkedIn Recruiter, own spreadsheets)."""

import io

import pandas as pd

# Field -> lowercase column names seen in common exports. First match wins.
ALIASES = {
    "full_name": ["full name", "full_name", "name", "candidate name", "ім'я", "піб"],
    "first_name": ["first name", "first_name", "firstname"],
    "last_name": ["last name", "last_name", "lastname"],
    "linkedin_url": ["linkedin url", "linkedin_url", "linkedin", "profile url", "linkedin profile", "public profile url"],
    "current_title": ["current title", "current_title", "title", "job title", "headline", "position", "посада"],
    "current_company": ["current company", "current_company", "company", "company name", "employer", "компанія"],
    "start_date": ["start date", "current position start date", "start_date", "position start", "дата початку"],
    "tenure_text": ["tenure", "time in role", "time in company", "years in current company", "стаж"],
    "location": ["location", "city", "country", "локація"],
    "email": ["email", "e-mail", "work email", "personal email"],
    "profile_text": ["summary", "about", "experience", "profile", "skills", "description", "опис"],
}

FIELD_LABELS = {
    "full_name": "Ім'я (повне)",
    "first_name": "Ім'я",
    "last_name": "Прізвище",
    "linkedin_url": "LinkedIn URL",
    "current_title": "Поточна посада",
    "current_company": "Поточна компанія",
    "start_date": "Дата старту в компанії",
    "tenure_text": "Стаж у компанії (текст)",
    "location": "Локація",
    "email": "Email",
    "profile_text": "Текст профілю / досвід",
}


def read_csv(data: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp1251", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc, dtype=str, sep=None, engine="python").fillna("")
        except UnicodeDecodeError:
            continue
    raise ValueError("Не вдалося прочитати CSV: невідоме кодування")


def guess_mapping(columns: list[str]) -> dict[str, list[str]]:
    """Return field -> list of matching columns. profile_text may combine several columns."""
    lower = {c.strip().lower(): c for c in columns}
    mapping: dict[str, list[str]] = {}
    for field, aliases in ALIASES.items():
        hits = [lower[a] for a in aliases if a in lower]
        if hits:
            mapping[field] = hits if field == "profile_text" else hits[:1]
    return mapping


def rows_from_df(df: pd.DataFrame, mapping: dict[str, list[str]], source: str) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        row = {}
        for field, cols in mapping.items():
            values = [str(r[c]).strip() for c in cols if c in df.columns and str(r[c]).strip()]
            if field == "profile_text":
                row[field] = "\n".join(f"{c}: {str(r[c]).strip()}" for c in cols if c in df.columns and str(r[c]).strip())
            else:
                row[field] = values[0] if values else ""
        if not row.get("full_name"):
            row["full_name"] = " ".join(x for x in (row.get("first_name", ""), row.get("last_name", "")) if x)
        row.pop("first_name", None)
        row.pop("last_name", None)
        if not row.get("full_name"):
            continue
        row["source"] = source
        rows.append(row)
    return rows
