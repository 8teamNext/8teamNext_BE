"""
이력서와 채용공고 파싱 결과물 비교 분석 (Leancage Analysis)

채용공고 URL 파싱 결과(JobInfo.to_dict() 형식)와 이력서 텍스트를 비교해
기술 매칭률, 보유/부족/잉여 기술, LLM 종합 평가를 반환합니다.
"""

import os
import json
from typing import List, Dict, Any

from openai import AsyncOpenAI

from services.parsers.base import extract_techs_from_text, TECH_ALIASES


# ─── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _normalize(raw: List[str]) -> List[str]:
    """tech_stack 원본 목록을 TECH_ALIASES 기준으로 정규화 후 정렬"""
    result = set()
    for item in raw:
        key = item.strip().lower()
        result.add(TECH_ALIASES.get(key, item.strip()))
    return sorted(result)


def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


# ─── LLM 종합 평가 ────────────────────────────────────────────────────────────

async def _generate_evaluation(
    match_rate: int,
    matched_skills: List[str],
    missing_skills: List[str],
    job_count: int,
) -> str:
    """gpt-4o-mini로 이력서-공고 비교 종합 평가 텍스트를 생성합니다."""
    context = {
        "overall_match_rate": match_rate,
        "total_jobs_analyzed": job_count,
        "matched_skills": matched_skills[:8],
        "missing_skills": missing_skills[:5],
    }

    prompt = f"""당신은 개발자 채용 전문 커리어 코치입니다. 아래 이력서-공고 기술 비교 데이터를 바탕으로 한국어로 실용적인 종합 평가 문장을 작성하세요.

분석 데이터:
{json.dumps(context, ensure_ascii=False, indent=2)}

규칙:
- 2~3문장으로 작성
- 전체 매칭률과 핵심 강점/보완점을 포함
- JSON 없이 평가 텍스트만 반환"""

    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        missing_preview = ", ".join(missing_skills[:3])
        if match_rate >= 80:
            return (
                f"분석한 {job_count}개 공고 대비 기술 매칭률이 {match_rate}%로 높습니다. "
                f"핵심 보유 기술 {', '.join(matched_skills[:3])} 등이 공고 요건과 잘 부합합니다."
            )
        elif match_rate >= 50:
            return (
                f"분석한 {job_count}개 공고 대비 기술 매칭률은 {match_rate}%입니다. "
                + (f"{missing_preview} 등 추가 보완이 권장됩니다." if missing_preview else "")
            )
        else:
            return (
                f"분석한 {job_count}개 공고 대비 기술 매칭률이 {match_rate}%로 낮습니다. "
                + (f"{missing_preview} 등 핵심 요구 기술 습득이 우선 필요합니다." if missing_preview else "")
            )


# ─── 메인 함수 ────────────────────────────────────────────────────────────────

async def leancage_analysis(
    resume_text: str,
    parsed_jobs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    이력서와 채용공고 파싱 결과물을 비교 분석합니다.

    Args:
        resume_text : 이력서 원문 텍스트
        parsed_jobs : 채용공고 파싱 결과 목록 (JobInfo.to_dict() 형식)
                      필드: url, title, company, job_type, tasks, tech_stack, raw_text, error

    Returns:
        match_rate          : 전체 공고 통합 기술 매칭률 (%) — 다른 함수의 fit_score/match_percentage 대응
        overall_evaluation  : LLM 기반 종합 평가 텍스트 — ResumeGithubResponse.overall_evaluation 대응
        resume_skills       : 이력서 보유 기술 목록
        job_required_skills : 전체 공고 요구 기술 합집합
        matched_skills      : 이력서-공고 교차 보유 기술 — verified_skills/proven_skills 대응
        missing_skills      : 이력서에 없는 공고 요구 기술 — missing_skills 대응 (공통 필드명)
        extra_skills        : 공고에 없는 이력서 보유 기술 — newly_discovered_skills/discovered_skills 대응
        job_comparisons     : 공고별 상세 비교 결과 — job_comparisons/company_rankings 대응
    """
    # 이력서 기술 추출 및 정규화
    resume_skills = _normalize(extract_techs_from_text(resume_text))
    resume_set = set(resume_skills)

    all_job_skills: set = set()
    job_comparisons: List[Dict[str, Any]] = []

    for job in parsed_jobs:
        if job.get("error"):
            continue

        # 공고 기술: tech_stack(파서 추출) + tasks/raw_text에서 추가 추출
        base_skills = list(job.get("tech_stack") or [])
        extra_text = " ".join(job.get("tasks") or []) + " " + (job.get("raw_text") or "")
        job_skills = set(_normalize(base_skills + extract_techs_from_text(extra_text)))

        all_job_skills.update(job_skills)

        matched = sorted(resume_set & job_skills)
        missing = sorted(job_skills - resume_set)
        extra = sorted(resume_set - job_skills)
        rate = int(len(matched) / max(len(job_skills), 1) * 100)

        job_comparisons.append({
            "url": job.get("url", ""),
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "job_type": job.get("job_type", ""),
            "match_rate": rate,
            "matched_skills": matched,
            "missing_skills": missing,
            "extra_skills": extra,
        })

    job_comparisons.sort(key=lambda x: x["match_rate"], reverse=True)

    # 전체 공고 통합 비교
    all_matched = sorted(resume_set & all_job_skills)
    all_missing = sorted(all_job_skills - resume_set)
    all_extra = sorted(resume_set - all_job_skills)
    overall_rate = int(len(all_matched) / max(len(all_job_skills), 1) * 100)

    overall_evaluation = await _generate_evaluation(
        overall_rate,
        all_matched,
        all_missing,
        len(job_comparisons),
    )

    return {
        "match_rate": overall_rate,
        "overall_evaluation": overall_evaluation,
        "resume_skills": resume_skills,
        "job_required_skills": sorted(all_job_skills),
        "matched_skills": all_matched,
        "missing_skills": all_missing,
        "extra_skills": all_extra,
        "job_comparisons": job_comparisons,
    }
