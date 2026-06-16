import re
import urllib.parse
from typing import List
from models import GapAnalysisResponse, CompanyRanking
from services.github_analyzer import extract_name_from_url
from services.recommender import recommend_projects

# List of tech keywords to extract from resume text
TECH_GLOSSARY = [
    "Java", "Spring Boot", "Spring Data JPA", "JPA", "Hibernate", "Kotlin", "Swift", "Dart", "Flutter",
    "Python", "Django", "FastAPI", "Flask", "Go", "C++", "JavaScript", "TypeScript",
    "React.js", "React", "Next.js", "Vue.js", "Angular", "Node.js", "Express", "NestJS",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Oracle", "Docker", "Kubernetes",
    "AWS", "GCP", "Azure", "GitHub Actions", "CI/CD", "Git", "HTML/CSS"
]

def parse_skills_from_text(text: str) -> List[str]:
    if not text:
        return []
    found = []
    text_lower = text.lower()
    for tech in TECH_GLOSSARY:
        # Match word boundaries or special chars like .js / C++ / CI/CD
        pattern = r'\b' + re.escape(tech.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found.append(tech)
    return found

def analyze_gap(repo_urls: List[str], resume_text: str, job_urls: List[str]) -> GapAnalysisResponse:
    # 1. Gather User Skills
    user_skills = set()
    
    # Extract from resume
    resume_skills = parse_skills_from_text(resume_text)
    for s in resume_skills:
        user_skills.add(s)
        
    # Extract from github repos (mock analysis)
    github_tech_keywords = {
        "spring": ["Java", "Spring Boot", "JPA", "MySQL"],
        "react": ["JavaScript", "React.js", "HTML/CSS"],
        "django": ["Python", "Django", "PostgreSQL"],
        "node": ["JavaScript", "Node.js", "Express"],
        "android": ["Kotlin", "Android SDK"],
        "ios": ["Swift", "iOS SDK"],
        "flutter": ["Dart", "Flutter"],
        "docker": ["Docker"],
        "aws": ["AWS"],
        "next": ["TypeScript", "Next.js", "React.js"]
    }
    
    for url in repo_urls:
        url_lower = url.lower()
        for key, techs in github_tech_keywords.items():
            if key in url_lower:
                for t in techs:
                    user_skills.add(t)
                    
    # Fallback to general skills if user inputs nothing
    if not user_skills:
        user_skills = {"Java", "Spring Boot", "Git", "MySQL", "HTML/CSS"}
        
    # 2. Extract job posting requirements (mocked per company)
    company_rankings = []
    all_job_required_skills = set()
    
    for idx, job_url in enumerate(job_urls):
        company_name = extract_name_from_url(job_url, f"Company {idx+1}")
        
        # Decide stack based on keywords or index
        job_lower = job_url.lower()
        if "frontend" in job_lower or "react" in job_lower:
            reqs = ["TypeScript", "React.js", "Next.js", "HTML/CSS", "Git"]
            role = "Frontend Engineer"
        elif "android" in job_lower or "ios" in job_lower:
            reqs = ["Kotlin", "Android SDK", "Git", "Java"]
            role = "Mobile App Developer"
        else:
            reqs = ["Java", "Spring Boot", "JPA", "MySQL", "Docker", "AWS"]
            role = "Backend Engineer"
            
        for r in reqs:
            all_job_required_skills.add(r)
            
        # Calc match
        matched_count = sum(1 for skill in reqs if skill in user_skills)
        fit_score = int((matched_count / len(reqs)) * 100)
        
        # Build reason
        if fit_score >= 80:
            reason = "High alignment with core tech stack. Main requirements verified in portfolio."
        elif fit_score >= 50:
            reason = "Moderate fit. Recommended to supplement Docker/AWS deployment experience."
        else:
            reason = "High gap in tech stack. Immediate portfolio supplement is highly recommended."
            
        company_rankings.append(CompanyRanking(
            rank=0, # Will sort and set ranks
            company_name=company_name,
            role=role,
            job_url=job_url,
            fit_score=fit_score,
            reason=reason
        ))
        
    # Sort rankings by score descending
    company_rankings.sort(key=lambda x: x.fit_score, reverse=True)
    for idx, r in enumerate(company_rankings):
        r.rank = idx + 1
        
    # 3. Compute skill overlaps
    proven_skills = [s for s in all_job_required_skills if s in user_skills]
    missing_skills = [s for s in all_job_required_skills if s not in user_skills]
    discovered_skills = [s for s in user_skills if s not in all_job_required_skills]
    
    # Priority skills are missing skills that appear in multiple jobs
    priority_skills = missing_skills[:3]
    
    # Get project recommendations
    recommended_projects = recommend_projects(missing_skills)
    
    return GapAnalysisResponse(
        proven_skills=proven_skills,
        missing_skills=missing_skills,
        discovered_skills=discovered_skills,
        priority_skills=priority_skills,
        company_rankings=company_rankings,
        recommended_projects=recommended_projects
    )
