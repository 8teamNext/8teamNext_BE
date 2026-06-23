from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# 1. GitHub Analysis Models
class GithubAnalysisRequest(BaseModel):
    repo_urls: List[str] = Field(..., max_items=5)
    job_urls: List[str] = Field(..., max_items=5)

class RepoDetail(BaseModel):
    name: str
    url: str
    primary_language: str
    languages: List[str]
    readme_status: str
    stars: int
    quality_score: int
    description: str
    commit_count: int = 0

class JobFitDetail(BaseModel):
    job_url: str
    company_name: str
    role: str
    match_percentage: int
    matched_skills: List[str]
    missing_skills: List[str]

class GithubAnalysisResponse(BaseModel):
    portfolio_rating: str
    overall_job_fit: int
    strong_skills: List[str]
    weak_skills: List[str]
    readme_suggestions: List[str]
    repo_details: List[RepoDetail]
    job_comparisons: List[JobFitDetail]
    total_commits: int = 0
    active_weeks: int = 0   # 최근 52주 중 커밋이 있는 주 수 (잔디)

# 2. Gap Analysis Models
class GapAnalysisRequest(BaseModel):
    repo_urls: Optional[List[str]] = []
    resume_text: Optional[str] = ""
    job_urls: List[str]

class CompanyRanking(BaseModel):
    rank: int
    company_name: str
    role: str
    job_url: str
    fit_score: int
    reason: str

class RecommendedProject(BaseModel):
    title: str
    description: str
    technologies: List[str]
    missing_skills_covered: List[str]
    difficulty: str
    impact: str
    architecture: str

class GapAnalysisResponse(BaseModel):
    proven_skills: List[str]
    missing_skills: List[str]
    discovered_skills: List[str]
    priority_skills: List[str]
    company_rankings: List[CompanyRanking]
    recommended_projects: List[RecommendedProject]

# 3. Resume-GitHub Link Models
class ResumeGithubRequest(BaseModel):
    resume_text: Optional[str] = None
    resume_url: Optional[str] = None
    github_username: str
    tech_stack: List[str]

class ResumeGithubResponse(BaseModel):
    overall_evaluation: str
    resume_skills: List[str]
    github_skills: List[str]
    verified_skills: List[str]         # present in both or verified by repo
    unverified_skills: List[str]       # resume-only, no github proof
    newly_discovered_skills: List[str] # github-only, not on resume
    supplement_advice: str = ""        # LLM 이력서 보완 권고
    update_suggestion: str = ""        # LLM 이력서 업데이트 제안

# 4. AI Interview Question Generator Models
class InterviewGenRequest(BaseModel):
    cover_letter: str
    job_posting: Optional[str] = ""

class InterviewQuestion(BaseModel):
    id: int
    category: str  # 기술 구현 | 트러블슈팅 | 시스템 설계 | 협업·소통 | CS 기초 | DevOps
    question: str
    intent: str  # why the interviewer asks this
    suggested_keywords: List[str]
    sample_answer_tip: str
    sample_answer: str

class JobPostingAnalysis(BaseModel):
    summary: str = ""                  # 회사·직무·공고 한 줄 요약
    skills: List[str] = []             # 잡코리아 스킬 섹션에서 직접 추출한 태그
    extracted_requirements: List[str]  # 채용공고에서 추출한 핵심 요구사항
    matched: List[str]                 # 자소서와 일치하는 역량
    unmatched: List[str]               # 자소서에 없는 역량 (갭)

class InterviewGenResponse(BaseModel):
    questions: List[InterviewQuestion]
    job_posting_analysis: Optional[JobPostingAnalysis] = None

# 5. Cover Letter Comparison Models
class CoverLetterCompareRequest(BaseModel):
    original_text: str
    improved_text: str

class CoverLetterCompareResponse(BaseModel):
    overall_summary: str
    improved_expressions: List[Dict[str, str]]  # e.g. [{"original": "...", "improved": "...", "reason": "..."}]
    added_experiences: List[str]
    strengthened_techs: List[str]
    remaining_gaps: List[str]

# 6. User Profile & Dashboard Models
class UserProfile(BaseModel):
    name: str = ""
    github_username: Optional[str] = ""
    default_resume: Optional[str] = ""
    default_cover_letter: Optional[str] = ""

class AnalysisHistoryItem(BaseModel):
    id: str
    type: str  # "github", "gap", "resume-github", "interview", "cover-letter"
    date: str
    summary: str

# 7. 종합 페이지 공통 포맷
class MetricItem(BaseModel):
    key: str
    label: str
    score: int
    detail: str

class ComparisonRaw(BaseModel):
    active_weeks: int
    total_commits: int
    repo_count: int
    matched_skills: List[str]
    unmatched_skills: List[str]

class ComparisonResult(BaseModel):
    service: str
    overall_score: int
    metrics: List[MetricItem]
    raw: ComparisonRaw
    ai_comment: str = ""

# 8. Unified Analysis Models
class UnifiedAnalysisRequest(BaseModel):
    github_url: str
    resume_text: str
    job_urls: List[str] = Field(..., max_items=5)

class UnifiedGithubPart(BaseModel):
    repo_count: int
    total_commits: int
    tech_stack: List[str]
    readme_quality: str
    project_completeness: str
    readme_suggestions: List[str]
    repo_details: List[RepoDetail]

class UnifiedResumePart(BaseModel):
    resume_quality: str
    tech_stack_matching: int
    verified_skills: List[str]
    unverified_skills: List[str]
    missing_skills: List[str]

class UnifiedGapPart(BaseModel):
    missing_technologies: List[str]
    learning_roadmap: List[str]

class UnifiedAnalysisResponse(BaseModel):
    portfolio_rating: str
    overall_match_pct: int      # 전체 매칭 비율 (가중 평균)
    skill_match_pct: int        # 기술스택 일치도 (GitHub ∩ 이력서 / 합집합 %)
    active_weeks: int           # 깃 커밋 활동 주 수 (최근 52주)
    total_commits: int          # 전체 커밋 수
    repo_coverage_pct: int      # 레포 기술 커버리지 (이력서 기술 사용 레포 비율 %)
    repo_count: int             # 공개 레포지토리 수
    github_analysis: UnifiedGithubPart
    resume_analysis: UnifiedResumePart
    skill_gap: UnifiedGapPart
    recommended_projects: List[RecommendedProject]
    comparison_result: ComparisonResult  # 종합 페이지 공통 포맷
