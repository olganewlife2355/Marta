"""Claude calls: build a scorecard from JD + kick-off, assess a candidate against it."""

import json
import os

import anthropic

from .models import CandidateAssessment, Scorecard

MODEL = os.environ.get("SOURCING_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

COMPANY_CONTEXT = os.environ.get(
    "SOURCING_COMPANY_CONTEXT",
    "StellarTech: B2C mobile subscription apps, edtech, publisher з performance marketing.",
)

SCORECARD_SYSTEM = f"""Ти senior технічний рекрутер. Компанія: {COMPANY_CONTEXT}
З опису вакансії та нотаток kick-off з хайринг-менеджером склади scorecard для сорсингу.
Правила:
- must_have: 3-7 критеріїв, які реально можна перевірити з LinkedIn-профілю.
- nice_to_have: 2-5 критеріїв.
- donor_companies: 10-25 компаній, звідки варто хантити. Tier 1: прямі конкуренти (b2c subscription mobile, edtech).
  Tier 2: суміжні b2c subscription / mobile продукти. Tier 3: інші релевантні (агенції, великі продуктові компанії).
  Якщо в kick-off названі конкретні компанії, обов'язково включи їх.
- Не вигадуй вимог, яких немає у вхідних даних; якщо чогось бракує, пиши загальноприйняте для ролі.
- Мова відповіді: українська, назви компаній і технологій як в оригіналі."""

ASSESS_SYSTEM = f"""Ти senior технічний рекрутер. Компанія: {COMPANY_CONTEXT}
Оціни кандидата за scorecard вакансії. Правила:
- Оцінюй лише за фактами з профілю. Немає даних = низька оцінка і evidence 'немає даних'.
- must_have_scores і nice_to_have_scores: по одному запису на кожен критерій scorecard, назва criterion точно як у scorecard.
- Оцінки 0-10.
- connection_note: коротка персональна нотатка до інвайту в LinkedIn (до 280 символів), з опорою на конкретику профілю,
  без тиску, без згадки зарплати, мовою, якою найімовірніше пише кандидат (за замовчуванням англійська).
- Мова summary: українська."""


class AIError(RuntimeError):
    pass


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _parse(system: str, user: str, output_format):
    try:
        response = _client().beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_format,
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise AIError("Невірний або відсутній ANTHROPIC_API_KEY") from e
    except anthropic.RateLimitError as e:
        raise AIError("Ліміт запитів до Claude, спробуйте за хвилину") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Помилка Claude API ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Немає з'єднання з Claude API") from e
    if response.stop_reason == "refusal":
        raise AIError("Claude відмовився обробити цей запит")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise AIError("Відповідь Claude обрізана або не розпізнана, спробуйте ще раз")
    return response.parsed_output


def build_scorecard(title: str, jd: str, kickoff: str) -> dict:
    user = f"Вакансія: {title}\n\n<jd>\n{jd}\n</jd>\n\n<kickoff_notes>\n{kickoff or 'немає'}\n</kickoff_notes>"
    return _parse(SCORECARD_SYSTEM, user, Scorecard).model_dump()


def assess_candidate(scorecard: dict, candidate: dict) -> dict:
    profile = {
        k: candidate.get(k)
        for k in ("full_name", "current_title", "current_company", "start_date", "tenure_text", "location", "profile_text")
        if candidate.get(k)
    }
    user = (
        f"<scorecard>\n{json.dumps(scorecard, ensure_ascii=False, indent=1)}\n</scorecard>\n\n"
        f"<candidate_profile>\n{json.dumps(profile, ensure_ascii=False, indent=1)}\n</candidate_profile>"
    )
    return _parse(ASSESS_SYSTEM, user, CandidateAssessment).model_dump()
