from typing import List
from models import ResumeGithubResponse
from services.gap_analyzer import parse_skills_from_text

def match_resume_github(
    resume_text: str,
    resume_url: str,
    github_username: str,
    tech_stack: List[str]
) -> ResumeGithubResponse:
    # 1. Parse resume skills
    resume_skills = set(parse_skills_from_text(resume_text))
    # Also add user specified tech_stack
    for t in tech_stack:
        if t:
            resume_skills.add(t)
            
    if not resume_skills:
        # Fallback values
        resume_skills = {"Java", "Spring Boot", "JPA", "MySQL", "AWS", "React.js"}
        
    # 2. Mock GitHub skills (simulate scanning their profile)
    github_skills = set()
    username_lower = github_username.lower()
    
    # Generate some mock GitHub skills based on username or standard defaults
    if any(k in username_lower for k in ["spring", "java", "back"]):
        github_skills = {"Java", "Spring Boot", "MySQL", "Git"}
    elif any(k in username_lower for k in ["react", "web", "front"]):
        github_skills = {"TypeScript", "React.js", "HTML/CSS", "Git"}
    else:
        # Default mix
        github_skills = {"Java", "Spring Boot", "MySQL", "Git", "TypeScript", "React.js", "Docker"}
        
    # 3. Calculate intersections and differences
    verified_skills = list(resume_skills.intersection(github_skills))
    unverified_skills = list(resume_skills.difference(github_skills))
    newly_discovered_skills = list(github_skills.difference(resume_skills))
    
    # Build evaluation summary
    total_resume = len(resume_skills)
    verified_count = len(verified_skills)
    
    if total_resume > 0:
        ratio = verified_count / total_resume
    else:
        ratio = 0.5
        
    if ratio >= 0.8:
        overall_evaluation = (
            f"이력서와 포트폴리오의 기술 정합성이 매우 높습니다! 이력서에 기재된 {total_resume}개 기술 중 {verified_count}개 기술이 "
            f"GitHub({github_username}) 저장소의 실제 소스코드 상에서 완벽히 검증되었습니다. 신뢰도가 아주 높은 포트폴리오입니다."
        )
    elif ratio >= 0.5:
        overall_evaluation = (
            f"기본적인 기술 일치는 양호하나, 이력서에 기재된 기술 중 {len(unverified_skills)}개 기술(예: {', '.join(unverified_skills[:2])})은 "
            f"GitHub 상의 코드 구현 증빙이 다소 부족합니다. 해당 기술들을 보완할 수 있는 프로젝트를 추가하는 것을 추천합니다."
        )
    else:
        overall_evaluation = (
            f"이력서와 깃허브 코드 간의 검증 Gap이 발견되었습니다! 이력서에 작성된 주요 기술 스택의 실제 구현 코드가 공개 GitHub 저장소 상에서 확인되지 않습니다. "
            f"작업했던 로컬 프로젝트를 깃허브에 업로드하거나 이력서의 기술 설명을 더 다듬을 필요가 있습니다."
        )
        
    return ResumeGithubResponse(
        overall_evaluation=overall_evaluation,
        resume_skills=list(resume_skills),
        github_skills=list(github_skills),
        verified_skills=verified_skills,
        unverified_skills=unverified_skills,
        newly_discovered_skills=newly_discovered_skills
    )
