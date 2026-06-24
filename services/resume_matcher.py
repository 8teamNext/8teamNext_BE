from typing import List, Set
from models import ResumeGithubResponse
from services.text_utils import parse_skills_from_text, normalize_skill


async def match_resume_github(
    resume_text: str,
    resume_url: str,
    github_username: str,
    github_skills: List[str],
    llm_skills: List[str] = None,  # LLM으로 추출한 기술 (없으면 키워드 매칭 사용)
) -> ResumeGithubResponse:
    # 1. 이력서 기술 추출: LLM 결과 우선, 없으면 키워드 매칭 폴백
    if llm_skills:
        resume_skills: Set[str] = set(llm_skills)
        print(f"  [resume_matcher] LLM 기술 사용: {sorted(resume_skills)}")
    else:
        resume_skills: Set[str] = set(parse_skills_from_text(resume_text))
        print(f"  [resume_matcher] 키워드 매칭 사용: {sorted(resume_skills)}")

    if not resume_skills:
        return ResumeGithubResponse(
            overall_evaluation="이력서에서 기술 스택을 추출할 수 없습니다. 이력서 내용을 확인해주세요.",
            resume_skills=[],
            github_skills=github_skills,
            verified_skills=[],
            unverified_skills=[],
            newly_discovered_skills=github_skills,
        )

    github_skills_set: Set[str] = set(github_skills)

    # 2. 정규화된 이름으로 비교 (HTML == HTML/CSS 등 alias 처리)
    norm_github: Set[str] = {normalize_skill(s) for s in github_skills_set}

    verified_skills = []
    unverified_skills = []
    for skill in sorted(resume_skills):
        if normalize_skill(skill) in norm_github:
            verified_skills.append(skill)
        else:
            unverified_skills.append(skill)

    # GitHub에만 있는 기술: 정규화 기준으로 이력서에 없는 것
    norm_resume: Set[str] = {normalize_skill(s) for s in resume_skills}
    newly_discovered_skills = sorted(s for s in github_skills_set if normalize_skill(s) not in norm_resume)

    total_resume = len(resume_skills)
    verified_count = len(verified_skills)
    ratio = verified_count / max(total_resume, 1)

    if ratio >= 0.8:
        overall_evaluation = (
            f"이력서와 GitHub 포트폴리오의 기술 정합성이 매우 높습니다. "
            f"이력서에 기재된 {total_resume}개 기술 중 {verified_count}개가 "
            f"GitHub({github_username}) 실제 코드에서 확인되었습니다."
        )
    elif ratio >= 0.5:
        examples = ', '.join(unverified_skills[:3])
        overall_evaluation = (
            f"기술 일치율이 양호하나, {len(unverified_skills)}개 기술({examples})은 "
            f"GitHub 코드로 증빙되지 않습니다. 해당 기술을 사용한 프로젝트를 추가하세요."
        )
    else:
        overall_evaluation = (
            f"이력서 기재 기술({total_resume}개) 중 GitHub에서 확인된 기술이 {verified_count}개에 불과합니다. "
            f"이력서 기술 스택과 실제 GitHub 코드 간 Gap이 큽니다."
        )

    return ResumeGithubResponse(
        overall_evaluation=overall_evaluation,
        resume_skills=sorted(resume_skills),
        github_skills=sorted(github_skills_set),
        verified_skills=verified_skills,
        unverified_skills=unverified_skills,
        newly_discovered_skills=newly_discovered_skills,
    )
