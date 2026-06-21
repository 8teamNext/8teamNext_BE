"""
이력서와 채용공고 파싱 결과물 비교 분석 (Leancage Analysis)

채용공고 URL 파싱 결과(JobInfo.to_dict() 형식)와 이력서 텍스트를 비교해
공통 포맷(service / overall_score / metrics / raw / detail)으로 반환합니다.

점수 배분 (공고별 100점):
  기술 매칭률    60% — TECH_ALIASES 키워드 기준, 가장 객관적
  담당업무 연관도 30% — 공고 tasks 도메인 키워드 ↔ 이력서 텍스트 매칭
  경력 조건 부합  10% — job_type ↔ 이력서 경력 감지, 규칙 기반
                        (가중치 낮은 이유: "무관" 공고가 많아 변별력 약함 + 휴리스틱 감지)
"""

import os
import re
import json
from typing import List, Dict, Any, TypedDict

from openai import AsyncOpenAI

from services.parsers.base import extract_techs_from_text, TECH_ALIASES


# ─── 점수 가중치 ─────────────────────────────────────────────────────────────

_WEIGHT_TECH   = 0.60
_WEIGHT_TASK   = 0.30
_WEIGHT_CAREER = 0.10


# ─── 타입 정의 ───────────────────────────────────────────────────────────────

class MetricItem(TypedDict):
    key: str
    label: str
    score: int
    detail: str


class LeancageRaw(TypedDict):
    match_rate: int
    matched_skills: List[str]
    missing_skills: List[str]
    extra_skills: List[str]
    overall_evaluation: str
    career_level: str


class JobComparison(TypedDict):
    url: str
    company: str
    title: str
    job_type: str
    overall_score: int
    tech_score: int
    task_score: int
    career_score: int
    matched_skills: List[str]
    missing_skills: List[str]
    extra_skills: List[str]


class LeancageDetail(TypedDict):
    resume_skills: List[str]
    job_required_skills: List[str]
    job_comparisons: List[JobComparison]


class LeancageResult(TypedDict):
    service: str
    overall_score: int
    metrics: List[MetricItem]
    raw: LeancageRaw
    detail: LeancageDetail


# ─── 경력 조건 ────────────────────────────────────────────────────────────────

_CAREER_PATTERNS = [
    r'\d+\s*년\s*(이상|경력|차)',   # "3년 이상", "5년 경력", "3년차"
    r'경력\s*\d+',                  # "경력 3년"
    r'(재직|재직중|前)',
    r'(주식회사|㈜|\(주\))',         # 회사명 패턴 → 재직 이력 있음
]

_NEWBIE_PATTERNS = [
    r'신입',
    r'졸업\s*예정',
    r'재학\s*중',
]

# (이력서 경력수준, 공고 job_type) → 점수
_CAREER_FIT_TABLE: Dict[tuple, int] = {
    ("경력", "경력"): 100,
    ("경력", "무관"): 100,
    ("경력", "신입"): 70,   # 오버스펙이지만 지원 가능
    ("경력", ""):     80,   # job_type 미감지 공고
    ("신입", "신입"): 100,
    ("신입", "무관"): 85,
    ("신입", "경력"): 20,   # 경력 요건 미충족 패널티
    ("신입", ""):     65,
    ("unknown", "무관"): 80,
    ("unknown", "신입"): 65,
    ("unknown", "경력"): 65,
    ("unknown", ""):     65,
}


def _detect_career_level(resume_text: str) -> str:
    """이력서 텍스트에서 신입/경력 여부를 규칙 기반으로 감지합니다."""
    for pattern in _CAREER_PATTERNS:
        if re.search(pattern, resume_text):
            return "경력"
    for pattern in _NEWBIE_PATTERNS:
        if re.search(pattern, resume_text):
            return "신입"
    return "unknown"


def _score_career_fit(career_level: str, job_type: str) -> int:
    return _CAREER_FIT_TABLE.get((career_level, job_type), 65)


# ─── 담당업무 연관도 ─────────────────────────────────────────────────────────

# 기술 스택 이외의 업무 도메인 키워드 (TECH_ALIASES와 겹치지 않는 것들 위주)
_DOMAIN_KEYWORDS = [
    # 개발 방법론
    "REST", "API", "MSA", "마이크로서비스", "CI/CD", "TDD", "애자일", "스크럼",
    # 인프라/운영
    "인프라", "배포", "운영", "모니터링", "자동화", "로그",
    # 데이터/성능
    "데이터", "분석", "쿼리", "최적화", "성능", "대용량", "트래픽", "고가용성",
    # 보안/인증
    "인증", "인가", "보안",
    # 협업/품질
    "코드 리뷰", "문서화",
    # 아키텍처
    "설계", "구축",
]


def _score_task_relevance(resume_text: str, tasks: List[str]) -> int:
    """공고 담당업무 키워드 중 이력서에도 등장하는 비율로 0~100 반환.
    tasks가 비어 있으면 파싱 실패로 간주해 중립 50 반환."""
    if not tasks:
        return 50

    tasks_lower = " ".join(tasks).lower()
    resume_lower = resume_text.lower()

    # tasks 텍스트에 등장하는 도메인 키워드만 추림
    task_keywords = [kw for kw in _DOMAIN_KEYWORDS if kw.lower() in tasks_lower]
    if not task_keywords:
        return 50

    matched = sum(1 for kw in task_keywords if kw.lower() in resume_lower)
    return int(matched / len(task_keywords) * 100)


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


def _weighted_score(tech: int, task: int, career: int) -> int:
    return int(tech * _WEIGHT_TECH + task * _WEIGHT_TASK + career * _WEIGHT_CAREER)


def _build_metrics(
    job_comparisons: List[JobComparison],
    all_matched: List[str],
    career_level: str,
) -> List[MetricItem]:
    if not job_comparisons:
        return [
            MetricItem(key="tech_match",     label="기술 매칭률",     score=0, detail="분석된 공고 없음"),
            MetricItem(key="task_relevance", label="담당업무 연관도", score=0, detail="분석된 공고 없음"),
            MetricItem(key="career_fit",     label="경력 조건 부합", score=0, detail="분석된 공고 없음"),
        ]

    n = len(job_comparisons)
    avg_tech   = int(sum(j["tech_score"]   for j in job_comparisons) / n)
    avg_task   = int(sum(j["task_score"]   for j in job_comparisons) / n)
    avg_career = int(sum(j["career_score"] for j in job_comparisons) / n)

    career_label = {"경력": "경력자", "신입": "신입", "unknown": "경력 미확인"}.get(career_level, career_level)

    tech_metric: MetricItem = {
        "key": "tech_match",
        "label": "기술 매칭률",
        "score": avg_tech,
        "detail": f"{n}개 공고 평균 · 매칭 기술 {len(all_matched)}개",
    }
    task_metric: MetricItem = {
        "key": "task_relevance",
        "label": "담당업무 연관도",
        "score": avg_task,
        "detail": f"{n}개 공고 평균 · 업무 도메인 키워드 기준",
    }
    career_metric: MetricItem = {
        "key": "career_fit",
        "label": "경력 조건 부합",
        "score": avg_career,
        "detail": f"이력서 감지: {career_label} · {n}개 공고 평균",
    }

    return [tech_metric, task_metric, career_metric]


# ─── LLM 종합 평가 ────────────────────────────────────────────────────────────

async def _generate_evaluation(
    overall_score: int,
    avg_tech: int,
    avg_task: int,
    avg_career: int,
    matched_skills: List[str],
    missing_skills: List[str],
    career_level: str,
    job_count: int,
) -> str:
    """gpt-4o-mini로 이력서-공고 비교 종합 평가 텍스트를 생성합니다."""
    context = {
        "overall_score": overall_score,
        "avg_tech_match": avg_tech,
        "avg_task_relevance": avg_task,
        "avg_career_fit": avg_career,
        "career_level": career_level,
        "total_jobs_analyzed": job_count,
        "matched_skills": matched_skills[:8],
        "missing_skills": missing_skills[:5],
    }

    prompt = f"""당신은 개발자 채용 전문 커리어 코치입니다. 아래 이력서-공고 비교 데이터를 바탕으로 한국어로 실용적인 종합 평가 문장을 작성하세요.

분석 데이터:
{json.dumps(context, ensure_ascii=False, indent=2)}

규칙:
- 2~3문장으로 작성
- 종합 점수, 기술 강점/보완점, 경력 적합성을 포함
- JSON 없이 평가 텍스트만 반환"""

    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        missing_preview = ", ".join(missing_skills[:3])
        if overall_score >= 80:
            return (
                f"{job_count}개 공고 종합 점수 {overall_score}점으로 높은 적합도를 보입니다. "
                f"{', '.join(matched_skills[:3])} 등 핵심 기술이 공고 요건과 잘 부합합니다."
            )
        elif overall_score >= 50:
            return (
                f"{job_count}개 공고 종합 점수 {overall_score}점입니다. "
                + (f"{missing_preview} 등 추가 보완이 권장됩니다." if missing_preview else "")
            )
        else:
            return (
                f"{job_count}개 공고 종합 점수 {overall_score}점으로 개선이 필요합니다. "
                + (f"{missing_preview} 등 핵심 기술 습득이 우선 필요합니다." if missing_preview else "")
            )


# ─── 메인 함수 ────────────────────────────────────────────────────────────────

async def leancage_analysis(
    resume_text: str,
    parsed_jobs: List[Dict[str, Any]],
) -> LeancageResult:
    """
    이력서와 채용공고 파싱 결과물을 비교 분석합니다.

    Args:
        resume_text : 이력서 원문 텍스트
        parsed_jobs : 채용공고 파싱 결과 목록 (JobInfo.to_dict() 형식, 최대 5개)
                      필드: url, title, company, job_type, tasks, tech_stack, raw_text, error

    Returns:
        LeancageResult 공통 포맷:
          overall_score  : 전체 공고 가중 평균 점수 (60% 기술 + 30% 업무 + 10% 경력)
          metrics        : [tech_match, task_relevance, career_fit] 공고 평균
          raw            : 집계 수치 및 LLM 총평
          detail         : 공고별 상세 (재호출 불필요)
    """
    resume_skills  = _normalize(extract_techs_from_text(resume_text))
    resume_set     = set(resume_skills)
    career_level   = _detect_career_level(resume_text)

    all_job_skills: set = set()
    job_comparisons: List[JobComparison] = []

    for job in parsed_jobs[:5]:
        if job.get("error"):
            continue

        base_skills  = list(job.get("tech_stack") or [])
        extra_text   = " ".join(job.get("tasks") or []) + " " + (job.get("raw_text") or "")
        job_skills   = set(_normalize(base_skills + extract_techs_from_text(extra_text)))
        all_job_skills.update(job_skills)

        matched = sorted(resume_set & job_skills)
        missing = sorted(job_skills - resume_set)
        extra   = sorted(resume_set - job_skills)

        tech_score   = int(len(matched) / max(len(job_skills), 1) * 100)
        task_score   = _score_task_relevance(resume_text, job.get("tasks") or [])
        career_score = _score_career_fit(career_level, job.get("job_type", ""))
        overall      = _weighted_score(tech_score, task_score, career_score)

        job_comparisons.append(JobComparison(
            url=job.get("url", ""),
            company=job.get("company", ""),
            title=job.get("title", ""),
            job_type=job.get("job_type", ""),
            overall_score=overall,
            tech_score=tech_score,
            task_score=task_score,
            career_score=career_score,
            matched_skills=matched,
            missing_skills=missing,
            extra_skills=extra,
        ))

    job_comparisons.sort(key=lambda x: x["overall_score"], reverse=True)

    all_matched = sorted(resume_set & all_job_skills)
    all_missing = sorted(all_job_skills - resume_set)
    all_extra   = sorted(resume_set - all_job_skills)

    n = len(job_comparisons)
    overall_score = int(sum(j["overall_score"] for j in job_comparisons) / n) if n else 0
    avg_tech      = int(sum(j["tech_score"]    for j in job_comparisons) / n) if n else 0
    avg_task      = int(sum(j["task_score"]    for j in job_comparisons) / n) if n else 0
    avg_career    = int(sum(j["career_score"]  for j in job_comparisons) / n) if n else 0

    overall_evaluation = await _generate_evaluation(
        overall_score, avg_tech, avg_task, avg_career,
        all_matched, all_missing, career_level, n,
    )

    metrics = _build_metrics(job_comparisons, all_matched, career_level)

    return LeancageResult(
        service="leancage",
        overall_score=overall_score,
        metrics=metrics,
        raw=LeancageRaw(
            match_rate=avg_tech,
            matched_skills=all_matched,
            missing_skills=all_missing,
            extra_skills=all_extra,
            overall_evaluation=overall_evaluation,
            career_level=career_level,
        ),
        detail=LeancageDetail(
            resume_skills=resume_skills,
            job_required_skills=sorted(all_job_skills),
            job_comparisons=job_comparisons,
        ),
    )
