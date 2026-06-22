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


async def generate_overall_evaluation(
    verified_skills: List[str],
    unverified_skills: List[str],
    newly_discovered_skills: List[str],
    match_pct: int,
    github_username: str,
) -> str:
    """이력서-GitHub 종합 평가 한 줄 요약 생성."""
    client = _get_client()

    prompt = f"""다음은 이력서와 GitHub 포트폴리오 비교 분석 결과입니다.

[분석 데이터]
- 기술 일치율: {match_pct}%
- GitHub에서 검증된 기술: {', '.join(verified_skills) if verified_skills else '없음'}
- 이력서에만 있고 GitHub 미검증 기술: {', '.join(unverified_skills) if unverified_skills else '없음'}
- GitHub에서 새로 발견된 기술: {', '.join(newly_discovered_skills) if newly_discovered_skills else '없음'}
- GitHub 사용자명: {github_username}

[작성 규칙]
- 반드시 2문장 이내로 작성
- 각 문장은 반드시 마침표로 완전하게 끝낼 것 (절대 "..." 나 미완성 문장 금지)
- 일치율 수치와 핵심 특징을 자연스럽게 포함
- 딱딱하지 않은 한국어 조언 톤"""

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [LLM] 종합 평가 생성 오류: {e}")
        if match_pct >= 80:
            return f"이력서와 GitHub 포트폴리오의 기술 정합성이 매우 높습니다! ({match_pct}% 일치)"
        elif match_pct >= 50:
            return f"기본적인 기술 일치는 양호하나 ({match_pct}%), 일부 기술의 GitHub 증빙이 부족합니다."
        else:
            return f"이력서와 GitHub 간의 기술 검증 Gap이 발견되었습니다 ({match_pct}% 일치)."


async def generate_resume_github_advice(
    verified_skills: List[str],
    unverified_skills: List[str],
    newly_discovered_skills: List[str],
    match_pct: int,
) -> dict:
    """이력서-GitHub 분석 결과를 바탕으로 LLM이 맞춤형 권고문을 생성.

    Returns:
        {
            "supplement_advice": str,  # 이력서 보완 권고
            "update_suggestion": str,  # 이력서 업데이트 제안
        }
    """
    client = _get_client()

    supplement_advice = ""
    update_suggestion = ""

    # 이력서 보완 권고 (미검증 기술이 있을 때만)
    if unverified_skills:
        prompt = f"""다음은 이력서-GitHub 포트폴리오 분석 결과입니다.

[분석 결과]
- GitHub에서 실제 확인된 기술: {', '.join(verified_skills) if verified_skills else '없음'}
- 이력서에 기재했지만 GitHub에서 확인 안 된 기술: {', '.join(unverified_skills)}
- 기술 일치율: {match_pct}%

[작성 규칙]
- 2~3문장으로 간결하게
- 미검증 기술을 구체적으로 언급하며 어떻게 증빙할 수 있는지 실용적으로 조언
- 예: 어떤 종류의 프로젝트를 만들어 올리면 좋은지 힌트 포함
- 딱딱하지 않은 조언 톤, 한국어로 작성"""

        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )
            supplement_advice = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"  [LLM] 보완 권고 생성 오류: {e}")
            supplement_advice = (
                f"{', '.join(unverified_skills)} 기술은 이력서에 기재되어 있지만 "
                "GitHub에서 실제 사용 증거가 확인되지 않았습니다. "
                "관련 프로젝트를 GitHub에 업로드해 증빙해보세요."
            )

    # 이력서 업데이트 제안 (GitHub에서 새로 발견된 기술이 있을 때만)
    if newly_discovered_skills:
        prompt = f"""다음은 이력서-GitHub 포트폴리오 분석 결과입니다.

[분석 결과]
- 이력서에는 없지만 GitHub에서 실제 사용이 확인된 기술: {', '.join(newly_discovered_skills)}
- 기술 일치율: {match_pct}%

[작성 규칙]
- 2~3문장으로 간결하게
- 발견된 기술을 이력서에 추가하면 어떤 점에서 유리한지 설명
- 기술별로 어떤 방식으로 이력서에 기재하면 좋을지 실용적인 조언 포함
- 딱딱하지 않은 조언 톤, 한국어로 작성"""

        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )
            update_suggestion = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"  [LLM] 업데이트 제안 생성 오류: {e}")
            update_suggestion = (
                f"GitHub에서 {', '.join(newly_discovered_skills)} 기술 사용이 확인되었지만 "
                "이력서에는 기재되지 않았습니다. 이력서에 추가하면 기술 정합성이 높아집니다."
            )

    return {
        "supplement_advice": supplement_advice,
        "update_suggestion": update_suggestion,
    }
