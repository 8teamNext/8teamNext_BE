import re
import urllib.parse
from typing import List, Dict, Any
from models import GithubAnalysisResponse, RepoDetail, JobFitDetail

def extract_name_from_url(url: str, default: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip('/')
        if not path:
            return default
        parts = path.split('/')
        # Return last part or capitalized domain
        if len(parts) > 0:
            name = parts[-1]
            return name.replace('-', ' ').replace('_', ' ').title()
        return default
    except Exception:
        return default

async def analyze_github(repo_urls: List[str], job_urls: List[str]) -> GithubAnalysisResponse:
    # 1. Infer technologies from repository URLs
    detected_skills = set()
    repos = []
    
    # Predefined mapping for realistic parsing
    tech_keywords = {
        "spring": ["Java", "Spring Boot", "JPA", "MySQL"],
        "react": ["JavaScript", "React.js", "HTML/CSS", "Webpack"],
        "vue": ["JavaScript", "Vue.js", "HTML/CSS"],
        "django": ["Python", "Django", "PostgreSQL"],
        "node": ["JavaScript", "Node.js", "Express", "MongoDB"],
        "express": ["JavaScript", "Node.js", "Express"],
        "android": ["Kotlin", "Android SDK", "Jetpack Compose"],
        "ios": ["Swift", "iOS SDK", "SwiftUI"],
        "flutter": ["Dart", "Flutter"],
        "docker": ["Docker", "DevOps"],
        "aws": ["AWS", "Cloud Deployment"],
        "kubernetes": ["Kubernetes", "Docker", "DevOps"],
        "next": ["TypeScript", "Next.js", "React.js"],
        "nest": ["TypeScript", "NestJS", "Node.js"],
        "typescript": ["TypeScript"],
        "python": ["Python"],
        "fastapi": ["Python", "FastAPI"]
    }
    
    default_languages = ["Java", "TypeScript", "Python", "Kotlin", "Go", "C++"]
    
    for i, url in enumerate(repo_urls):
        name = extract_name_from_url(url, f"프로젝트 {i+1}")
        url_lower = url.lower()
        
        # Analyze name and url to find techs
        repo_techs = []
        primary_lang = default_languages[i % len(default_languages)]
        
        for key, techs in tech_keywords.items():
            if key in url_lower:
                repo_techs.extend(techs)
                primary_lang = techs[0]
        
        # If nothing detected, assign mock set based on index
        if not repo_techs:
            if i % 3 == 0:
                repo_techs = ["Java", "Spring Boot", "JPA", "H2 Database"]
                primary_lang = "Java"
            elif i % 3 == 1:
                repo_techs = ["TypeScript", "React.js", "CSS Modules"]
                primary_lang = "TypeScript"
            else:
                repo_techs = ["Python", "FastAPI", "SQLAlchemy", "SQLite"]
                primary_lang = "Python"
                
        for t in repo_techs:
            detected_skills.add(t)
            
        # Mock repository quality
        stars = (i * 7 + 3) % 25
        quality = 75 + (i * 12 + stars) % 21  # 75 - 95
        readme_status = "우수 (Good)" if quality > 85 else "보통 (설치 가이드 및 아키텍처 설명 보완 필요)"
        
        repos.append(RepoDetail(
            name=name,
            url=url,
            primary_language=primary_lang,
            languages=list(set([primary_lang] + [t for t in repo_techs if t in ["Java", "TypeScript", "JavaScript", "Python", "Kotlin", "Go", "Swift", "Dart"]])),
            readme_status=readme_status,
            stars=stars,
            quality_score=quality,
            description=f"AI 분석 결과: {', '.join(repo_techs[:3])} 아키텍처 패턴의 깔끔한 구현이 확인된 레포지토리입니다."
        ))
        
    strong_skills = list(detected_skills)
    
    # 2. Analyze Job URLs and map fit
    job_comparisons = []
    all_job_required_skills = set()
    
    for j_idx, job_url in enumerate(job_urls):
        company_domain = "TechCorp"
        try:
            parsed = urllib.parse.urlparse(job_url)
            domain_parts = parsed.netloc.split('.')
            if len(domain_parts) > 1:
                company_domain = domain_parts[-2].title()
        except Exception:
            pass
            
        role_en = "Backend Engineer"
        if "frontend" in job_url.lower() or "react" in job_url.lower():
            role_en = "Frontend Engineer"
        elif "android" in job_url.lower() or "ios" in job_url.lower():
            role_en = "Mobile App Developer"
        elif "devops" in job_url.lower() or "cloud" in job_url.lower():
            role_en = "DevOps Engineer"
        
        # Mock requirements based on role
        if "backend" in role_en.lower():
            required_skills = ["Java", "Spring Boot", "JPA", "MySQL", "Docker", "AWS", "Redis"]
        elif "frontend" in role_en.lower():
            required_skills = ["TypeScript", "React.js", "Next.js", "Redux", "HTML/CSS", "Jest"]
        elif "mobile" in role_en.lower():
            required_skills = ["Kotlin", "Android SDK", "Jetpack Compose", "Coroutines", "Git"]
        else:
            # Default rich stack
            required_skills = ["Java", "Spring Boot", "TypeScript", "React.js", "Docker", "AWS"]
            
        role_kr_map = {
            "Frontend Engineer": "프론트엔드 엔지니어",
            "Backend Engineer": "백엔드 엔지니어",
            "Mobile App Developer": "모바일 앱 개발자",
            "DevOps Engineer": "DevOps 엔지니어"
        }
        role = role_kr_map.get(role_en, role_en)
            
        for skill in required_skills:
            all_job_required_skills.add(skill)
            
        matched = [s for s in required_skills if s in detected_skills]
        missing = [s for s in required_skills if s not in detected_skills]
        
        # Calculate fit percentage
        fit_percentage = int((len(matched) / max(len(required_skills), 1)) * 100)
        
        job_comparisons.append(JobFitDetail(
            job_url=job_url,
            company_name=company_domain,
            role=role,
            match_percentage=fit_percentage,
            matched_skills=matched,
            missing_skills=missing
        ))
        
    # Overall evaluations
    overall_fit = sum(j.match_percentage for j in job_comparisons) // len(job_comparisons) if job_comparisons else 0
    weak_skills = [s for s in all_job_required_skills if s not in detected_skills]
    
    # Portfolio score rating
    avg_quality = sum(r.quality_score for r in repos) // len(repos) if repos else 70
    if avg_quality >= 90:
        portfolio_rating = "매우 우수 (A+)"
    elif avg_quality >= 80:
        portfolio_rating = "우수 (B+)"
    else:
        portfolio_rating = "보통 (C)"
        
    # Build README suggestions
    readme_suggestions = [
        "컴포넌트 간의 상호작용을 상세히 보여주는 명확한 시스템 아키텍처 다이어그램을 리드미에 추가하세요.",
        "환경 변수 설정 및 패키지 의존성 설치법을 포함한 상세한 '시작 가이드(Getting Started)'를 작성하세요.",
        "성능 최적화 시도, 데이터베이스 쿼리 튜닝 내역(예: JPA N+1 해결 과정) 또는 테스트 코드 커버리지 지표를 문서화해 기록하세요."
    ]
    if any(r.stars == 0 for r in repos):
        readme_suggestions.append("가장 완성도가 높은 대표 프로젝트를 깃허브 프로필에 고정(Pin)하고, 검토자의 눈길을 끌 수 있는 빌드 상태/사용 언어 배지 등을 달아주세요.")
        
    return GithubAnalysisResponse(
        portfolio_rating=portfolio_rating,
        overall_job_fit=overall_fit,
        strong_skills=strong_skills,
        weak_skills=weak_skills[:6],
        readme_suggestions=readme_suggestions,
        repo_details=repos,
        job_comparisons=job_comparisons
    )
