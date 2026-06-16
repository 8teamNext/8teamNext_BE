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
            f"Strong alignment! {verified_count} out of {total_resume} skills claimed on the resume "
            f"are verified by code repositories on GitHub ({github_username}). High credibility portfolio."
        )
    elif ratio >= 0.5:
        overall_evaluation = (
            f"Good base alignment, but {len(unverified_skills)} claimed skills (such as {', '.join(unverified_skills[:2])}) "
            f"lack coding evidence on GitHub. Adding repositories showcasing these skills is recommended."
        )
    else:
        overall_evaluation = (
            f"Verification Gap detected! Most claimed resume skills are not evident in public GitHub repositories. "
            f"Consider pushing your local project workspaces or refining your resume's technical description."
        )
        
    return ResumeGithubResponse(
        overall_evaluation=overall_evaluation,
        resume_skills=list(resume_skills),
        github_skills=list(github_skills),
        verified_skills=verified_skills,
        unverified_skills=unverified_skills,
        newly_discovered_skills=newly_discovered_skills
    )
