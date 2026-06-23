"""
LLM 서비스
- GitHub 언어 비중 + topics + package_skills → 프레임워크 추론
- gpt-4o-mini 사용
- Constrained Output + JSON Mode + Few-shot
- username 단위 인메모리 캐싱 (15분)
"""

import os
import json
from openai import AsyncOpenAI
from cachetools import TTLCache

from services.parsers.base import TECH_ALIASES

# username 단위 캐시 (최대 100개, 15분)
_cache: TTLCache = TTLCache(maxsize=100, ttl=900)

# TECH_ALIASES에서 허용 기술 목록 추출 (중복 제거)
ALLOWED_SKILLS = sorted(set(TECH_ALIASES.values()))


# ── 프롬프트 구성 ─────────────────────────────────────────────────────────
def build_prompt(
    languages: dict[str, float],
    topics: list[str],
    package_skills: list[str],
) -> str:
    top_langs = list(languages.items())[:5]
    lang_str = ", ".join([f"{lang} {ratio}%" for lang, ratio in top_langs])
    topic_str = ", ".join(topics[:10]) if topics else "없음"
    package_str = ", ".join(package_skills) if package_skills else "없음"
    allowed_str = ", ".join(ALLOWED_SKILLS)

    return f"""당신은 GitHub 데이터를 분석해 개발자의 기술스택을 추론하는 전문가입니다.

아래 규칙을 반드시 따르세요:
1. confirmed: GitHub API에서 직접 확인된 언어만 포함
2. inferred: 언어 비중, topics, package.json 의존성을 근거로 사용했을 가능성이 있는 프레임워크/라이브러리 포함
3. 반드시 아래 허용 목록에 있는 기술만 사용할 것 (목록에 없는 기술은 절대 포함하지 말 것)
4. package.json 의존성에 있는 기술은 적극적으로 inferred에 포함할 것
5. topics에 언급된 기술도 적극적으로 inferred에 포함할 것
6. inferred는 비어있지 않도록 최대한 추론할 것
7. JSON만 반환할 것 (설명, 주석 없이)

허용 기술 목록:
{allowed_str}

예시 1)
입력 언어: JavaScript 70.0%, CSS 30.0%
입력 topics: react, redux
입력 package.json: React, Redux
출력: {{"confirmed": ["JavaScript"], "inferred": ["React"]}}

예시 2)
입력 언어: TypeScript 60.0%, JavaScript 30.0%, CSS 10.0%
입력 topics: nextjs, vercel
입력 package.json: Next.js, React, TypeScript
출력: {{"confirmed": ["TypeScript", "JavaScript"], "inferred": ["Next.js", "React"]}}

예시 3)
입력 언어: Python 90.0%, Dockerfile 10.0%
입력 topics: fastapi, docker
입력 package.json: 없음
출력: {{"confirmed": ["Python"], "inferred": ["FastAPI", "Docker"]}}

예시 4)
입력 언어: Java 80.0%, HTML 20.0%
입력 topics: spring, jpa
입력 package.json: 없음
출력: {{"confirmed": ["Java"], "inferred": ["Spring Boot", "Spring"]}}

실제 입력)
입력 언어: {lang_str}
입력 topics: {topic_str}
입력 package.json: {package_str}
출력:"""


# ── LLM 호출 ─────────────────────────────────────────────────────────────
async def _call_llm(
    languages: dict[str, float],
    topics: list[str],
    package_skills: list[str],
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    client = AsyncOpenAI(api_key=api_key)

    prompt = build_prompt(languages, topics, package_skills)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=300,
        temperature=0.2,  # 약간 높여서 추론 범위 확대
    )

    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


# ── 결과 검증 ─────────────────────────────────────────────────────────────
def _validate(
    result: dict,
    languages: dict[str, float],
    package_skills: list[str],
) -> dict:
    allowed_set = set(ALLOWED_SKILLS)

    confirmed = [
        skill for skill in result.get("confirmed", [])
        if skill in allowed_set
    ]
    inferred = [
        skill for skill in result.get("inferred", [])
        if skill in allowed_set
    ]

    # GitHub API 언어는 무조건 confirmed에 포함
    for lang in languages.keys():
        if lang in allowed_set and lang not in confirmed:
            confirmed.append(lang)

    # package.json에서 찾은 기술은 inferred에 강제 추가
    for skill in package_skills:
        if skill in allowed_set and skill not in confirmed and skill not in inferred:
            inferred.append(skill)

    # inferred에서 confirmed 중복 제거
    inferred = [s for s in inferred if s not in confirmed]

    return {
        "confirmed": sorted(confirmed),
        "inferred": sorted(inferred),
    }


# ── 메인 진입점 ───────────────────────────────────────────────────────────
async def infer_skills(
    username: str,
    languages: dict[str, float],
    topics: list[str],
    package_skills: list[str] = [],
) -> dict:
    """
    username 단위 캐싱 적용
    같은 username 15분 내 재요청 시 LLM 호출 스킵

    반환:
    {
        "confirmed": ["JavaScript", "TypeScript"],
        "inferred": ["React", "Next.js"],
    }
    """
    # 캐시 확인
    if username in _cache:
        return _cache[username]

    try:
        result = await _call_llm(languages, topics, package_skills)
        validated = _validate(result, languages, package_skills)
    except Exception:
        # LLM 실패 시 confirmed + package_skills 반환
        allowed_set = set(ALLOWED_SKILLS)
        confirmed = sorted([
            lang for lang in languages.keys()
            if lang in allowed_set
        ])
        inferred = sorted([
            s for s in package_skills
            if s in allowed_set and s not in confirmed
        ])
        validated = {"confirmed": confirmed, "inferred": inferred}

    # 캐시 저장
    _cache[username] = validated

    return validated