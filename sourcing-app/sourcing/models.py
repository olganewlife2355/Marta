"""Pydantic models used for Claude structured outputs and in-app data."""

from typing import List

from pydantic import BaseModel, Field


class Criterion(BaseModel):
    name: str = Field(description="Коротка назва критерію, напр. 'iOS Swift 4+ роки'")
    description: str = Field(description="Що саме перевіряємо в профілі")
    weight: int = Field(description="Вага від 1 до 5, де 5 найважливіше")


class DonorCompany(BaseModel):
    name: str = Field(description="Назва компанії, як її пишуть у LinkedIn")
    tier: int = Field(description="1 = прямий конкурент, 2 = суміжний b2c/subscription, 3 = інші релевантні")
    reason: str = Field(description="Чому ця компанія донор")


class Scorecard(BaseModel):
    role_summary: str
    seniority: str
    target_titles: List[str]
    must_have: List[Criterion]
    nice_to_have: List[Criterion]
    red_flags: List[str]
    donor_companies: List[DonorCompany]
    locations: List[str]


class CriterionScore(BaseModel):
    criterion: str
    score: int = Field(description="0-10")
    evidence: str = Field(description="Цитата або факт з профілю; 'немає даних', якщо не знайдено")


class CandidateAssessment(BaseModel):
    must_have_scores: List[CriterionScore]
    nice_to_have_scores: List[CriterionScore]
    domain_fit: int = Field(description="0-10: b2c, subscription, mobile, edtech, performance marketing")
    seniority_fit: int = Field(description="0-10: відповідність рівню вакансії")
    donor_companies_in_history: List[str] = Field(
        description="Компанії-донори зі scorecard, де кандидат працював раніше (не поточна)"
    )
    red_flags_found: List[str]
    summary: str = Field(description="2-3 речення: чому так оцінено")
    connection_note: str = Field(
        description="Персональна нотатка до інвайту в LinkedIn, до 280 символів, без згадки зарплати"
    )
