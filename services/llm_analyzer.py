import os
import asyncio
from typing import List
from openai import AsyncOpenAI


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


async def extract_skills_from_resume(resume_text: str) -> List[str]:
    """이력서 텍스트에서 기술 스택을 LLM으로 추출."""
    client = _get_client()
    prompt = f"""다음 이력서 텍스트에서 기술 스택(프로그래밍 언어, 프레임워크, 라이브러리, 데이터베이스, 인프라 도구 등)만 추출해줘.

규칙:
- 기술명만 콤마로 구분해서 한 줄로 출력 (설명 없이)
- 원어 표기 유지 (예: Java, Spring Boot, MySQL, Docker)
- 한글 기술명은 영어로 변환 (예: 스프링 → Spring Boot)
- 자격증, 학력, 회사명은 제외

이력서:
{resume_text[:3000]}

출력 예시: Java, Spring Boot, MySQL, Docker, AWS, Git"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        skills = [s.strip() for s in raw.split(",") if s.strip()]
        return skills
    except Exception as e:
        print(f"  [LLM] 기술 추출 오류: {e}")
        return []


async def generate_analysis_comment(
    skill_match_pct: int,
    commit_activity_pct: int,
    repo_coverage_pct: int,
    overall_score: int,
    matched_skills: List[str],
    unmatched_skills: List[str],
    total_commits: int,
    active_weeks: int,
    repo_count: int,
) -> str:
    """분석 수치를 바탕으로 개인화된 총평을 생성."""
    client = _get_client()
    prompt = f"""다음은 지원자의 이력서와 GitHub 포트폴리오를 비교 분석한 결과입니다.
이 데이터를 바탕으로 지원자에게 도움이 되는 구체적인 총평을 한국어로 작성해줘.

[분석 데이터]
- 기술스택 일치도: {skill_match_pct}% (이력서 기술 중 GitHub에서 증명된 비율)
- 깃 커밋 활동: {commit_activity_pct}% ({active_weeks}/52주 활동, 총 {total_commits}커밋)
- 레포 기술 커버리지: {repo_coverage_pct}% (이력서 기술이 사용된 레포 비율)
- 전체 매칭 비율: {overall_score}%
- GitHub에서 증명된 기술: {', '.join(matched_skills) if matched_skills else '없음'}
- 이력서에만 있고 GitHub 증빙 없는 기술: {', '.join(unmatched_skills) if unmatched_skills else '없음'}
- 공개 레포지토리 수: {repo_count}개

[작성 규칙]
- 5~8문장으로 작성 (너무 짧지 않게)
- 잘한 점 1~2가지를 먼저 구체적으로 언급
- 보완이 필요한 점 2~3가지를 기술명과 함께 구체적으로 제안
- GitHub에서 증빙되지 않은 기술은 포트폴리오 프로젝트로 보완하라고 조언
- 커밋 활동이 적다면 꾸준한 커밋 습관 조언
- 딱딱하지 않고 실질적인 도움이 되는 조언 톤으로"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [LLM] 총평 생성 오류: {e}")
        return ""
