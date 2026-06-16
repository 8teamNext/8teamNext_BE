import uuid
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from models import (
    GithubAnalysisRequest, GithubAnalysisResponse,
    GapAnalysisRequest, GapAnalysisResponse,
    ResumeGithubRequest, ResumeGithubResponse,
    InterviewGenRequest, InterviewGenResponse,
    CoverLetterCompareRequest, CoverLetterCompareResponse,
    UserProfile, AnalysisHistoryItem
)

# Import services
from services.github_analyzer import analyze_github
from services.gap_analyzer import analyze_gap
from services.resume_matcher import match_resume_github
from services.interview_gen import generate_interview_questions
from services.cover_letter_cmp import compare_cover_letters

app = FastAPI(
    title="AI Career Copilot API",
    description="Backend service providing AI-driven career gap analysis and resume feedback.",
    version="1.0.0"
)

# Configure CORS so Vite React frontend (typically port 5173) can access endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development convenience
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
db_profile = UserProfile(
    email="user@example.com",
    name="김코딩",
    github_username="kimcoding-dev",
    default_resume="""[김코딩 - 백엔드 개발자 이력서]
이메일: user@example.com | GitHub: github.com/kimcoding-dev

[기술 스택]
Java, Spring Boot, Spring Data JPA, MySQL, Git, Docker, HTML/CSS

[프로젝트 경험]
1. 도서 대여 관리 시스템 API (개인 프로젝트)
- Spring Boot와 Spring Data JPA를 사용해 백엔드 API 설계
- H2 데이터베이스 및 MySQL을 연동해 영속성 계층 구현
- RESTful 규칙에 따른 API 엔드포인트 설계

2. 포토 갤러리 공유 플랫폼 (팀 프로젝트)
- 프론트엔드 HTML/CSS 및 자바스크립트 구현 담당
- Spring Boot 백엔드 서버 연동 및 REST API 요청 데이터 바인딩
""",
    default_cover_letter="""어릴 적부터 컴퓨터를 조작하고 새로운 프로그램을 구동하는 것에 흥미가 깊었습니다. 
대학교 재학 중 웹 프로그래밍 과목을 수강하면서 웹 백엔드 시스템 개발에 매력을 느끼게 되었습니다. 
이후 독학으로 Spring Boot 프레임워크를 학습하며 여러 REST API 서버를 구현해보았습니다. 

특히 데이터가 저장되고 데이터베이스 쿼리가 수행되는 흐름에 관심이 많아 JPA와 관련된 강의를 듣고 실습했습니다. 
프로젝트 과정에서 팀원들과 적극적으로 의견을 주고받으며 협업하여 성공적으로 배포한 경험이 있습니다.
신입 백엔드 개발자로서 맡은 일에 성실히 책임을 다하며 회사와 함께 빠르게 성장하고 싶습니다.
"""
)

db_history: List[AnalysisHistoryItem] = [
    AnalysisHistoryItem(
        id="hist-1",
        type="github",
        date="2026-06-12 14:30",
        summary="GitHub Repository 분석 (A+ 등급, 72% 적합도)"
    ),
    AnalysisHistoryItem(
        id="hist-2",
        type="resume-github",
        date="2026-06-13 11:15",
        summary="이력서-GitHub 연계 신뢰성 분석 완료 (일치율 75%)"
    )
]

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Welcome to AI Career Copilot API. Visit /docs for documentation."}

@app.post("/api/analyze/github", response_model=GithubAnalysisResponse)
def api_analyze_github(payload: GithubAnalysisRequest):
    try:
        response = analyze_github(payload.repo_urls, payload.job_urls)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="github",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"GitHub 분석: 매칭 적합도 {response.overall_job_fit}%"
        )
        db_history.insert(0, new_hist)
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub analysis failed: {str(e)}"
        )

@app.post("/api/analyze/gap", response_model=GapAnalysisResponse)
def api_analyze_gap(payload: GapAnalysisRequest):
    try:
        # If resume_text is empty, fallback to the saved profile resume
        resume = payload.resume_text if payload.resume_text else db_profile.default_resume
        
        response = analyze_gap(payload.repo_urls, resume, payload.job_urls)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="gap",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"Gap 분석: 입증 기술 {len(response.proven_skills)}개, 부족 기술 {len(response.missing_skills)}개"
        )
        db_history.insert(0, new_hist)
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gap analysis failed: {str(e)}"
        )

@app.post("/api/analyze/resume-github", response_model=ResumeGithubResponse)
def api_analyze_resume_github(payload: ResumeGithubRequest):
    try:
        resume = payload.resume_text if payload.resume_text else db_profile.default_resume
        response = match_resume_github(
            resume,
            payload.resume_url,
            payload.github_username,
            payload.tech_stack
        )
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="resume-github",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"이력서-GitHub 분석: 검증완료 {len(response.verified_skills)}개"
        )
        db_history.insert(0, new_hist)
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume-GitHub linkage analysis failed: {str(e)}"
        )

@app.post("/api/analyze/interview-questions", response_model=InterviewGenResponse)
def api_analyze_interview_questions(payload: InterviewGenRequest):
    try:
        cover_letter = payload.cover_letter if payload.cover_letter else db_profile.default_cover_letter
        response = generate_interview_questions(cover_letter)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="interview",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"면접 질문 생성: {len(response.questions)}개 질문 추출"
        )
        db_history.insert(0, new_hist)
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Interview question generation failed: {str(e)}"
        )

@app.post("/api/analyze/cover-letter-compare", response_model=CoverLetterCompareResponse)
def api_analyze_cover_letter_compare(payload: CoverLetterCompareRequest):
    try:
        response = compare_cover_letters(payload.original_text, payload.improved_text)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="cover-letter",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"자소서 비교 분석 완료: 개선된 표현 {len(response.improved_expressions)}개"
        )
        db_history.insert(0, new_hist)
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cover letter comparison failed: {str(e)}"
        )

# --- Profile and History Session endpoints ---

@app.get("/api/profile", response_model=UserProfile)
def get_profile():
    return db_profile

@app.post("/api/profile", response_model=UserProfile)
def update_profile(profile: UserProfile):
    global db_profile
    db_profile = profile
    return db_profile

@app.get("/api/history", response_model=List[AnalysisHistoryItem])
def get_history():
    return db_history

@app.delete("/api/history/{id}")
def delete_history_item(id: str):
    global db_history
    db_history = [item for item in db_history if item.id != id]
    return {"status": "success", "message": "History item deleted"}
