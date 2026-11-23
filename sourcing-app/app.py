"""Sourcing & scoring desk. Run: streamlit run app.py"""

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    """Minimal .env loader so the user only edits one file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(APP_DIR / ".env")

from sourcing import ai, db, importer, service  # noqa: E402  (env must be loaded first)
from sourcing.scoring import DEFAULT_WEIGHTS  # noqa: E402

st.set_page_config(page_title="Sourcing Desk", page_icon="🎯", layout="wide")


@st.cache_resource
def get_conn():
    return db.connect()


conn = get_conn()
HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

WEIGHT_LABELS = {
    "must_have": "Must-have критерії",
    "nice_to_have": "Nice-to-have",
    "donor": "Компанія-донор",
    "domain": "Домен (b2c, subscription, mobile, edtech)",
    "seniority": "Сеньйорність",
}


def vacancy_picker(key: str):
    vacancies = db.list_vacancies(conn)
    if not vacancies:
        st.info("Спершу створіть вакансію у розділі «Вакансії».")
        return None
    options = {f"{v['title']} (#{v['id']})": v["id"] for v in vacancies}
    label = st.selectbox("Вакансія", list(options), key=key)
    return db.get_vacancy(conn, options[label])


# ---------------------------------------------------------------- pages

def page_vacancies():
    st.header("Вакансії та scorecard")
    with st.expander("➕ Нова вакансія", expanded=not db.list_vacancies(conn)):
        with st.form("new_vacancy"):
            title = st.text_input("Назва вакансії")
            jd = st.text_area("Опис вакансії (JD)", height=200)
            kickoff = st.text_area(
                "Нотатки kick-off з хайринг-менеджером (можна вставити транскрипт з Metaview)",
                height=200,
            )
            if st.form_submit_button("Зберегти") and title.strip():
                vid = db.add_vacancy(conn, title.strip(), jd, kickoff)
                st.success(f"Вакансію створено (#{vid}). Тепер згенеруйте scorecard нижче.")

    vacancy = vacancy_picker("vac_page")
    if not vacancy:
        return

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🤖 Згенерувати scorecard з JD + kick-off", disabled=not HAS_KEY):
            with st.spinner("Claude аналізує вакансію..."):
                try:
                    sc = ai.build_scorecard(vacancy["title"], vacancy["jd"], vacancy["kickoff"])
                    db.update_vacancy(conn, vacancy["id"], scorecard=sc)
                    st.rerun()
                except ai.AIError as e:
                    st.error(str(e))
        if not HAS_KEY:
            st.caption("Немає ANTHROPIC_API_KEY: заповніть scorecard вручну або додайте ключ у файл .env")
    with c2:
        if st.button("🗑 Видалити вакансію"):
            db.delete_vacancy(conn, vacancy["id"])
            st.rerun()

    with st.expander("JD та kick-off"):
        st.text(vacancy["jd"] or "—")
        st.divider()
        st.text(vacancy["kickoff"] or "—")

    sc = vacancy["scorecard"] or {
        "role_summary": "", "seniority": "", "target_titles": [], "must_have": [],
        "nice_to_have": [], "red_flags": [], "donor_companies": [], "locations": [],
    }

    st.subheader("Scorecard (можна редагувати)")
    role_summary = st.text_area("Суть ролі", sc["role_summary"], height=80)
    c1, c2 = st.columns(2)
    seniority = c1.text_input("Сеньйорність", sc["seniority"])
    titles = c2.text_input("Цільові тайтли (через кому)", ", ".join(sc["target_titles"]))
    locations = c1.text_input("Локації (через кому)", ", ".join(sc["locations"]))
    red_flags = c2.text_area("Red flags (кожен з нового рядка)", "\n".join(sc["red_flags"]), height=100)

    crit_cfg = {
        "name": st.column_config.TextColumn("Критерій", required=True),
        "description": st.column_config.TextColumn("Що перевіряємо"),
        "weight": st.column_config.NumberColumn("Вага 1-5", min_value=1, max_value=5, step=1, default=3),
    }
    st.markdown("**Must-have**")
    must = st.data_editor(
        pd.DataFrame(sc["must_have"], columns=["name", "description", "weight"]),
        num_rows="dynamic", column_config=crit_cfg, width="stretch", key=f"must_{vacancy['id']}",
    )
    st.markdown("**Nice-to-have**")
    nice = st.data_editor(
        pd.DataFrame(sc["nice_to_have"], columns=["name", "description", "weight"]),
        num_rows="dynamic", column_config=crit_cfg, width="stretch", key=f"nice_{vacancy['id']}",
    )
    st.markdown("**Компанії-донори**")
    donors = st.data_editor(
        pd.DataFrame(sc["donor_companies"], columns=["name", "tier", "reason"]),
        num_rows="dynamic",
        column_config={
            "name": st.column_config.TextColumn("Компанія", required=True),
            "tier": st.column_config.NumberColumn("Tier 1-3", min_value=1, max_value=3, step=1, default=2),
            "reason": st.column_config.TextColumn("Чому донор"),
        },
        width="stretch", key=f"donors_{vacancy['id']}",
    )

    st.markdown("**Ваги фінального скору**")
    weights = dict(vacancy["weights"] or DEFAULT_WEIGHTS)
    cols = st.columns(len(WEIGHT_LABELS))
    for col, (k, label) in zip(cols, WEIGHT_LABELS.items()):
        weights[k] = col.number_input(label, 0, 100, int(weights.get(k, 0)), step=5, key=f"w_{k}_{vacancy['id']}")

    if st.button("💾 Зберегти scorecard", type="primary"):
        def records(df):
            return [
                {k: (int(v) if k in ("weight", "tier") and pd.notna(v) else ("" if pd.isna(v) else v)) for k, v in r.items()}
                for r in df.dropna(subset=["name"]).to_dict("records")
                if str(r["name"]).strip()
            ]

        new_sc = {
            "role_summary": role_summary,
            "seniority": seniority,
            "target_titles": [t.strip() for t in titles.split(",") if t.strip()],
            "locations": [t.strip() for t in locations.split(",") if t.strip()],
            "red_flags": [t.strip() for t in red_flags.splitlines() if t.strip()],
            "must_have": records(must),
            "nice_to_have": records(nice),
            "donor_companies": records(donors),
        }
        db.update_vacancy(conn, vacancy["id"], scorecard=new_sc, weights=weights)
        st.success("Збережено. Перерахуйте скоринг у «Шортлисті», якщо змінили критерії або ваги.")


def page_import():
    st.header("Імпорт кандидатів")
    vacancy = vacancy_picker("imp_page")
    if not vacancy:
        return

    tab_csv, tab_manual = st.tabs(["CSV (Juicebox / LinkedIn Recruiter / таблиця)", "Додати вручну"])
    with tab_csv:
        up = st.file_uploader("CSV-файл", type=["csv"])
        if up:
            try:
                df = importer.read_csv(up.getvalue())
            except ValueError as e:
                st.error(str(e))
                return
            st.caption(f"Рядків: {len(df)}. Перевірте відповідність колонок.")
            guess = importer.guess_mapping(list(df.columns))
            mapping = {}
            cols = st.columns(3)
            for i, (field, label) in enumerate(importer.FIELD_LABELS.items()):
                col = cols[i % 3]
                if field == "profile_text":
                    mapping[field] = col.multiselect(label, list(df.columns), default=guess.get(field, []))
                else:
                    opts = ["—"] + list(df.columns)
                    default = guess.get(field, ["—"])[0]
                    choice = col.selectbox(label, opts, index=opts.index(default), key=f"map_{field}")
                    if choice != "—":
                        mapping[field] = [choice]
            st.dataframe(df.head(5), width="stretch")
            if st.button("Імпортувати", type="primary"):
                rows = importer.rows_from_df(df, mapping, source=up.name)
                for row in rows:
                    db.attach(conn, vacancy["id"], db.upsert_candidate(conn, row))
                st.success(f"Імпортовано {len(rows)} кандидатів у «{vacancy['title']}». Далі: «Шортлист» → «Оцінити».")

    with tab_manual:
        with st.form("manual_candidate", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data = {
                "full_name": c1.text_input("Ім'я"),
                "linkedin_url": c2.text_input("LinkedIn URL"),
                "current_title": c1.text_input("Поточна посада"),
                "current_company": c2.text_input("Поточна компанія"),
                "start_date": c1.text_input("Старт у компанії (2023-05 або May 2023)"),
                "location": c2.text_input("Локація"),
                "profile_text": st.text_area("Вставте текст профілю (About + Experience)", height=200),
                "source": "manual",
            }
            if st.form_submit_button("Додати") and data["full_name"].strip():
                db.attach(conn, vacancy["id"], db.upsert_candidate(conn, data))
                st.success("Додано.")


def run_scoring(vacancy, rows, use_ai: bool):
    bar = st.progress(0.0, text="Оцінюю...")
    errors = []
    for i, r in enumerate(rows, 1):
        try:
            service.score_candidate(conn, vacancy, r["candidate_id"], use_ai=use_ai)
        except ai.AIError as e:
            errors.append(f"{r['full_name']}: {e}")
            if "ANTHROPIC_API_KEY" in str(e):
                break
        bar.progress(i / len(rows), text=f"Оцінено {i}/{len(rows)}")
    bar.empty()
    for e in errors:
        st.error(e)


def page_shortlist():
    st.header("Шортлист і скоринг")
    vacancy = vacancy_picker("sl_page")
    if not vacancy:
        return
    if not vacancy["scorecard"]:
        st.warning("У вакансії ще немає scorecard. Створіть його у розділі «Вакансії».")
        return

    rows = [service.enrich_row(r, vacancy["scorecard"]) for r in db.pipeline_rows(conn, vacancy["id"])]
    if not rows:
        st.info("Кандидатів ще немає. Додайте їх у розділі «Імпорт».")
        return

    unscored = [r for r in rows if not r["assessment"]]
    c1, c2, c3 = st.columns(3)
    if c1.button(f"🤖 Оцінити нових через Claude ({len(unscored)})", disabled=not (HAS_KEY and unscored), type="primary"):
        run_scoring(vacancy, unscored, use_ai=True)
        st.rerun()
    if c2.button("🔁 Переоцінити всіх через Claude", disabled=not HAS_KEY):
        run_scoring(vacancy, rows, use_ai=True)
        st.rerun()
    if c3.button("⚡ Швидкий скор без AI (донори)"):
        run_scoring(vacancy, unscored, use_ai=False)
        st.rerun()

    f1, f2, f3 = st.columns(3)
    min_score = f1.slider("Мінімальний скор", 0, 100, 0)
    only_huntable = f2.checkbox("Тільки 12+ міс. у компанії", value=False)
    statuses = f3.multiselect("Статус", db.STATUSES)

    view = [
        r for r in rows
        if (r["score"] or 0) >= min_score
        and (not only_huntable or (r["tenure_months"] or 0) >= 12)
        and (not statuses or r["status"] in statuses)
    ]
    table = pd.DataFrame([
        {
            "Скор": r["score"],
            "Оцінка": "AI" if r["assessment"] else ("лише донор" if r["score"] is not None else "—"),
            "Хант": r["hunt_badge"],
            "Ім'я": r["full_name"],
            "Посада": r["current_title"],
            "Компанія": r["current_company"],
            "Донор": r["donor_tier"],
            "Міс. у компанії": r["tenure_months"],
            "Статус": r["status"],
            "LinkedIn": r["linkedin_url"],
        }
        for r in view
    ])
    st.dataframe(
        table, width="stretch", hide_index=True,
        column_config={
            "Скор": st.column_config.ProgressColumn("Скор", min_value=0, max_value=100, format="%d"),
            "LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="профіль"),
        },
    )
    st.caption("🟢 12-36 міс.: вікно для хантингу · 🟡 36+ міс.: перевірити стагнацію · 🔴 до 12 міс. · ⚪ немає даних")
    st.caption("«лише донор»: попередній скор тільки за компанією-донором (T1=100, T2=70, T3=40), без аналізу профілю.")

    st.subheader("Картки кандидатів")
    for r in view:
        title = f"{r['hunt_badge']} {r['score'] if r['score'] is not None else '—'} · {r['full_name']} · {r['current_title']} @ {r['current_company']}"
        with st.expander(title):
            candidate_card(vacancy, r)


def candidate_card(vacancy, r):
    a = r["assessment"]
    st.write(r["hunt_hint"])
    if r["linkedin_url"]:
        st.link_button("Відкрити профіль у LinkedIn", r["linkedin_url"])
    if a:
        st.markdown(f"**Висновок:** {a['summary']}")
        parts = a.get("parts", {})
        st.caption(" · ".join(f"{WEIGHT_LABELS[k]}: {round(v)}" for k, v in parts.items() if v is not None))
        crit = pd.DataFrame(
            [{"Тип": "Must", **s} for s in a["must_have_scores"]]
            + [{"Тип": "Nice", **s} for s in a["nice_to_have_scores"]]
        )
        if not crit.empty:
            st.dataframe(crit.rename(columns={"criterion": "Критерій", "score": "0-10", "evidence": "Доказ"}),
                         hide_index=True, width="stretch")
        if a["donor_companies_in_history"]:
            st.write("Донори в минулому досвіді:", ", ".join(a["donor_companies_in_history"]))
        if a["red_flags_found"]:
            st.warning("Red flags: " + "; ".join(a["red_flags_found"]))
        st.text_area("Нотатка до інвайту", a["connection_note"], key=f"note_{vacancy['id']}_{r['candidate_id']}")
    pipeline_controls(vacancy, r, prefix="card")


def pipeline_controls(vacancy, r, prefix: str):
    key = f"{prefix}_{vacancy['id']}_{r['candidate_id']}"
    c1, c2 = st.columns(2)
    status = c1.selectbox("Статус", db.STATUSES, index=db.STATUSES.index(r["status"]), key=f"st_{key}")
    current_touch = date.fromisoformat(r["next_touch"]) if r["next_touch"] else None
    touch = c2.date_input("Наступний дотик", value=current_touch, key=f"nt_{key}")
    notes = st.text_area("Нотатки", r["notes"] or "", key=f"nn_{key}", height=80)
    if st.button("Зберегти", key=f"save_{key}"):
        db.update_pipeline(conn, vacancy["id"], r["candidate_id"], status=status,
                           next_touch=touch.isoformat() if touch else None, notes=notes)
        st.rerun()


def page_connect_today():
    st.header("Кого додати в LinkedIn сьогодні")
    st.caption(
        "Застосунок нічого не надсилає в LinkedIn сам: це порушує правила LinkedIn і ризикує баном акаунта. "
        "Відкриваєте профіль, вставляєте нотатку, тиснете «Інвайт надіслано»."
    )
    vacancy = vacancy_picker("ct_page")
    if not vacancy:
        return
    c1, c2, c3 = st.columns(3)
    daily = c1.number_input("Скільки на сьогодні", 1, 50, 15)
    min_score = c2.slider("Мінімальний скор", 0, 100, 60)
    weekly_limit = c3.number_input("Ваш тижневий ліміт інвайтів", 10, 300, 100)

    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    sent_week = sum(
        1 for r in db.pipeline_rows(conn)
        if r["status"] == "Інвайт надіслано" and r["updated_at"] >= week_ago
    )
    st.metric("Інвайтів за 7 днів (за статусами)", f"{sent_week} / {weekly_limit}")

    rows = [service.enrich_row(r, vacancy["scorecard"]) for r in db.pipeline_rows(conn, vacancy["id"])]
    hunt_rank = {"🟢": 0, "🟡": 1, "⚪": 2, "🔴": 3}
    queue = sorted(
        [r for r in rows if r["status"] == "Новий" and (r["score"] or 0) >= min_score and r["assessment"]],
        key=lambda r: (hunt_rank[r["hunt_badge"]], -(r["score"] or 0)),
    )[: max(0, min(daily, weekly_limit - sent_week))]
    if not queue:
        st.info("Черга порожня: оцініть кандидатів у «Шортлисті» або знизьте мінімальний скор.")
    for r in queue:
        with st.container(border=True):
            st.markdown(f"**{r['hunt_badge']} {r['score']} · {r['full_name']}**: {r['current_title']} @ {r['current_company']} {r['donor_tier']}")
            st.code(r["assessment"]["connection_note"], language=None)
            c1, c2 = st.columns(2)
            if r["linkedin_url"]:
                c1.link_button("Відкрити профіль", r["linkedin_url"])
            if c2.button("✅ Інвайт надіслано", key=f"sent_{vacancy['id']}_{r['candidate_id']}"):
                follow = (date.today() + timedelta(days=7)).isoformat()
                db.update_pipeline(conn, vacancy["id"], r["candidate_id"], status="Інвайт надіслано", next_touch=follow)
                st.rerun()


def page_reminders():
    st.header("Нагадування і теплий нетворк")
    today = date.today().isoformat()
    rows = db.pipeline_rows(conn)
    due = [r for r in rows if r["next_touch"] and r["next_touch"] <= today and r["status"] not in ("Найнятий", "Не підходить")]
    st.subheader(f"На сьогодні: {len(due)}")
    for r in due:
        vacancy = {"id": r["vacancy_id"]}
        with st.expander(f"{r['next_touch']} · {r['full_name']} · {r['status']} · {r['vacancy_title']}"):
            if r["linkedin_url"]:
                st.link_button("Профіль", r["linkedin_url"])
            pipeline_controls(vacancy, r, prefix="rem")

    st.subheader("Теплий нетворк")
    warm = [r for r in rows if r["status"] in ("Конект", "Відповів", "Теплий", "Not now")]
    if warm:
        st.dataframe(pd.DataFrame([
            {"Ім'я": r["full_name"], "Компанія": r["current_company"], "Статус": r["status"],
             "Вакансія": r["vacancy_title"], "Скор": r["score"], "Наступний дотик": r["next_touch"],
             "Email": r["email"], "LinkedIn": r["linkedin_url"]}
            for r in warm
        ]), hide_index=True, width="stretch",
            column_config={"LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="профіль")})
    else:
        st.info("Поки нікого. Статуси «Конект», «Відповів», «Теплий», «Not now» потрапляють сюди.")


def page_settings():
    st.header("Налаштування та експорт")
    st.write("Claude API ключ:", "✅ знайдено" if HAS_KEY else "❌ немає (файл .env, див. README)")
    st.write("Модель:", ai.MODEL)
    st.write("База даних:", str(db.DB_PATH))
    rows = db.pipeline_rows(conn)
    if rows:
        export = pd.DataFrame([{k: v for k, v in r.items() if k != "assessment"} for r in rows])
        st.download_button("⬇️ Експорт пайплайну в CSV", export.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"pipeline_{date.today()}.csv", mime="text/csv")


PAGES = {
    "📋 Вакансії": page_vacancies,
    "📥 Імпорт": page_import,
    "🏆 Шортлист": page_shortlist,
    "🤝 Кого додати сьогодні": page_connect_today,
    "⏰ Нагадування": page_reminders,
    "⚙️ Налаштування": page_settings,
}

with st.sidebar:
    st.title("🎯 Sourcing Desk")
    page = st.radio("Розділ", list(PAGES), label_visibility="collapsed")
    if not HAS_KEY:
        st.warning("Немає ANTHROPIC_API_KEY: AI-скоринг вимкнено")

PAGES[page]()
