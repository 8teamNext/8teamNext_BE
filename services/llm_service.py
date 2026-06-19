"""
LLM 서비스
- GitHub 언어 비중 + topics → 프레임워크 추론
- gpt-4o-mini 사용
- Constrained Output + JSON Mode + Few-shot
- username 단위 인메모리 캐싱 (15분)
"""

import os
import json
from openai import AsyncOpenAI
from cachetools import TTLCache

from services.parsers.base import TECH_ALIASES

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# username 단위 캐시 (최대 100개, 15분)
_cache: TTLCache = TTLCache(maxsize=100, ttl=900)

# TECH_ALIASES에서 허용 기술 목록 추출 (중복 제거)
ALLOWED_SKILLS = sorted(set(TECH_ALIASES.values()))


#  프롬프트 구성
def build_prompt(languages: dict[str, float], topics: list[str]) -> str:
    # 상위 5개 언어만
    top_langs = list(languages.items())[:5]
    lang_str = ", ".join([f"{lang} {ratio}%" for lang, ratio in top_langs])
    topic_str = ", ".join(topics[:10]) if topics else "없음"
    allowed_str = ", ".join(ALLOWED_SKILLS)

    return f"""당신은 GitHub 데이터를 분석해 개발자의 기술스택을 추론하는 전문가입니다.

아래 규칙을 반드시 따르세요:
1. confirmed: GitHub API에서 직접 확인된 언어만 포함
2. inferred: 언어 비중과 topics를 근거로 사용했을 가능성이 높은 프레임워크/라이브러리만 포함
3. 반드시 아래 허용 목록에 있는 기술만 사용할 것 (목록에 없는 기술은 절대 포함하지 말 것)
4. 확실하지 않은 기술은 포함하지 말 것
5. JSON만 반환할 것 (설명, 주석 없이)

허용 기술 목록:
{allowed_str}

예시 1)
입력 언어: JavaScript 70.0%, CSS 30.0%
입력 topics: react, redux
출력: {{"confirmed": ["JavaScript"], "inferred": ["React"]}}

예시 2)
입력 언어: TypeScript 60.0%, JavaScript 30.0%, CSS 10.0%
입력 topics: nextjs, vercel
출력: {{"confirmed": ["TypeScript", "JavaScript"], "inferred": ["Next.js", "React"]}}

예시 3)
입력 언어: Python 90.0%, Dockerfile 10.0%
입력 topics: fastapi, docker
출력: {{"confirmed": ["Python"], "inferred": ["FastAPI", "Docker"]}}

실제 입력)
입력 언어: {lang_str}
입력 topics: {topic_str}
출력:"""


# LLM 호출
async def _call_llm(languages: dict[str, float], topics: list[str]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    client = AsyncOpenAI(api_key=api_key)  # 여기서 초기화
    
    prompt = build_prompt(languages, topics)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=300,
        temperature=0.1,
    )

    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


def _validate(result: dict, languages: dict[str, float]) -> dict:
    """
    - confirmed / inferred 키 없으면 기본값
    - 허용 목록에 없는 기술 필터링
    - confirmed에 언어 직접 추가 (LLM이 빠뜨릴 경우 대비)
    """
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

    # inferred에서 confirmed 중복 제거
    inferred = [s for s in inferred if s not in confirmed]

    return {
        "confirmed": sorted(confirmed),
        "inferred": sorted(inferred),
    }


#  메인 진입점 
async def infer_skills(username: str, languages: dict[str, float], topics: list[str]) -> dict:
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
        result = await _call_llm(languages, topics)
        validated = _validate(result, languages)
    except Exception:
        # LLM 실패 시 confirmed만 반환 (graceful degradation)
        allowed_set = set(ALLOWED_SKILLS)
        confirmed = sorted([
            lang for lang in languages.keys()
            if lang in allowed_set
        ])
        validated = {"confirmed": confirmed, "inferred": []}

    # 캐시 저장
    _cache[username] = validated

    return validated