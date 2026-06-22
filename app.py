from dotenv import load_dotenv
load_dotenv()
import uuid
from datetime import datetime
from typing import List, Dict, Any
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from services.crawler import crawler_bp 
from services.github_analyzer import analyze_github
from services.github_service import test_github
from services.llm_service import infer_skills
from services.matching_service import match_all

from models import (
    GithubAnalysisRequest, GithubAnalysisResponse,
    GapAnalysisRequest, GapAnalysisResponse,
    ResumeGithubRequest, ResumeGithubResponse,
    InterviewGenRequest, InterviewGenResponse,
    CoverLetterCompareRequest, CoverLetterCompareResponse,
    UserProfile, AnalysisHistoryItem,
    UnifiedAnalysisRequest, UnifiedAnalysisResponse
)

# Import services
from services.github_analyzer import analyze_github
from services.gap_analyzer import analyze_gap
from services.resume_matcher import match_resume_github
from services.resume_analysis import analyze_resume_github, extract_pdf_text, validate_resume_text
from services.interview_gen import generate_interview_questions
from services.cover_letter_cmp import compare_cover_letters

app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# In-memory session store (빈 상태로 시작 — 사용자가 마이페이지에서 직접 입력)
db_profile = UserProfile()

db_history: List[AnalysisHistoryItem] = []

# --- Endpoints ---

@app.route("/", methods=["GET"])
def read_root():
    return jsonify({"message": "Welcome to AI Career Copilot API. Visit /docs for documentation."})

# @app.route('/api/recruit', methods=['GET'])
# def get_recruitment():

CORS(app, resources={r"/*": {"origins": "*"}})
app.register_blueprint(crawler_bp)

@app.route("/api/analyze/github", methods=["POST"])
async def api_analyze_github():
    try:
        data = request.get_json()
        payload = GithubAnalysisRequest.model_validate(data)
        response = await analyze_github(payload.repo_urls, payload.job_urls)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="github",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"GitHub 분석: 매칭 적합도 {response.overall_job_fit}%"
        )
        db_history.insert(0, new_hist)
        
        return jsonify(response.model_dump())
    except Exception as e:
        return jsonify({"detail": f"GitHub analysis failed: {str(e)}"}), 500
    
# """
#     POST /api/analyze
#     body: {
#         "github_username": "kimcoding",
#         "job_urls": ["https://www.jobkorea.co.kr/..."]
#     }
 
#     반환:
#     {
#         "github": {
#             "username": "kimcoding",
#             "confirmed_skills": ["TypeScript", "JavaScript"],
#             "inferred_skills": ["React", "Next.js"],
#             "raw_languages": {"TypeScript": 60.5, ...}
#         },
#         "matching": [
#             {
#                 "url_index": 0,
#                 "status": "success",
#                 "title": "프론트엔드 개발자",
#                 "company": "회사명",
#                 "job_type": "신입",
#                 "jd_total": 3,
#                 "confirmed_score": 66.7,
#                 "inferred_score": 33.3,
#                 "confirmed_matched": ["TypeScript"],
#                 "inferred_matched": ["React"],
#                 "missing": ["Docker"],
#                 "extra_confirmed": ["JavaScript"]
#             }
#         ]
#     }
#     """

@app.route("/api/analyze", methods=["POST"])
async def api_analyze():
    data = request.get_json(silent=True)
 
    # 검증
    if not data:
        return jsonify({"error": "요청 body가 없습니다."}), 400
 
    github_username = data.get("github_username", "").strip()
    job_urls = data.get("job_urls", [])
 
    if not github_username:
        return jsonify({"error": "github_username이 필요합니다."}), 400
 
    if not isinstance(job_urls, list) or len(job_urls) == 0:
        return jsonify({"error": "job_urls는 1개 이상이어야 합니다."}), 400
 
    if len(job_urls) > 5:
        return jsonify({"error": "job_urls는 최대 5개까지 가능합니다."}), 400
 
    for url in job_urls:
        if not isinstance(url, str) or not url.startswith("http"):
            return jsonify({"error": f"올바르지 않은 URL: {url}"}), 400
 
    # GitHub 분석 + 크롤링 병렬 실행
    import asyncio
    from services.github_service import test_github
    from services.llm_service import infer_skills
    from services.parsers.parser_router import parse_job
 
    async def crawl_all(urls: list[str]) -> list[dict]:
        tasks = [parse_job(url) for url in urls]
        results = await asyncio.gather(*tasks)
        crawl_results = []
        for i, result in enumerate(results):
            d = result.to_dict()
            if d.get("error"):
                crawl_results.append({
                    "url_index": i,
                    "status": "failed",
                    "error": d["error"],
                })
            else:
                crawl_results.append({
                    "url_index": i,
                    "status": "success",
                    "title": d.get("title", ""),
                    "company": d.get("company", ""),
                    "job_type": d.get("job_type", ""),
                    "tech_stack": d.get("tech_stack", []),
                })
        return crawl_results
 
    async def github_analyze(username: str) -> dict:
        github_result = await test_github(username)
        if github_result.get("error"):
            return {"error": github_result["error"]}
        skill_result = await infer_skills(
            username=username,
            languages=github_result["languages"],
            topics=github_result["topics"],
        )
        return {
            "username": username,
            "confirmed_skills": skill_result["confirmed"],
            "inferred_skills": skill_result["inferred"],
            "raw_languages": github_result["languages"],
            "error": None,
        }
 
    # 병렬 실행
    crawl_result, github_result = await asyncio.gather(
        crawl_all(job_urls),
        github_analyze(github_username),
    )
 
    # GitHub 분석 실패
    if github_result.get("error"):
        status = 404 if "찾을 수 없습니다" in github_result["error"] else 400
        return jsonify({"error": github_result["error"]}), status
 
    # 매칭 계산
    matching = match_all(
        confirmed_skills=github_result["confirmed_skills"],
        inferred_skills=github_result["inferred_skills"],
        crawl_results=crawl_result,
    )
 
    return jsonify({
        "github": {
            "username": github_result["username"],
            "confirmed_skills": github_result["confirmed_skills"],
            "inferred_skills": github_result["inferred_skills"],
            "raw_languages": github_result["raw_languages"],
        },
        "matching": matching,
    })





@app.route("/api/analyze/gap", methods=["POST"])
async def api_analyze_gap():
    try:
        data = request.get_json()
        payload = GapAnalysisRequest.model_validate(data)

        # If resume_text is empty, fallback to the saved profile resume
        resume = payload.resume_text if payload.resume_text else db_profile.default_resume

        response = await analyze_gap(payload.repo_urls, resume, payload.job_urls)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="gap",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"Gap 분석: 입증 기술 {len(response.proven_skills)}개, 부족 기술 {len(response.missing_skills)}개"
        )
        db_history.insert(0, new_hist)
        
        return jsonify(response.model_dump())
    except Exception as e:
        return jsonify({"detail": f"Gap analysis failed: {str(e)}"}), 500

@app.route("/api/analyze/resume-github", methods=["POST"])
async def api_analyze_resume_github():
    try:
        data = request.get_json()
        payload = ResumeGithubRequest.model_validate(data)
        resume = payload.resume_text if payload.resume_text else db_profile.default_resume
        response = await analyze_resume_github(
            resume,
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
        
        return jsonify(response.model_dump())
    except Exception as e:
        return jsonify({"detail": f"Resume-GitHub linkage analysis failed: {str(e)}"}), 500


@app.route("/api/validate-resume", methods=["POST"])
async def api_validate_resume():
    data = request.get_json() or {}
    text = data.get("text", "")
    return jsonify(await validate_resume_text(text))


@app.route("/api/parse-resume", methods=["POST"])
async def api_parse_resume():
    if 'file' not in request.files:
        return jsonify({"detail": "파일이 없습니다."}), 400
    f = request.files['file']
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ('pdf', 'txt', 'md'):
        return jsonify({"detail": "파일 양식을 확인해주세요. (지원 형식: PDF, TXT, MD)"}), 400
    if ext != 'pdf':
        return jsonify({"detail": "파일 양식을 확인해주세요. 텍스트 파일은 브라우저에서 직접 읽습니다."}), 400
    try:
        text = await extract_pdf_text(f.read())
        if not text:
            return jsonify({"detail": "PDF에서 텍스트를 추출할 수 없습니다. 스캔 이미지 PDF는 지원되지 않습니다."}), 422
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"detail": f"PDF 파싱 실패: {str(e)}"}), 500


@app.route("/api/analyze/interview-questions", methods=["POST"])
async def api_analyze_interview_questions():
    try:
        data = request.get_json()
        payload = InterviewGenRequest.model_validate(data)
        cover_letter = payload.cover_letter if payload.cover_letter else db_profile.default_cover_letter
        response = await generate_interview_questions(cover_letter)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="interview",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"면접 질문 생성: {len(response.questions)}개 질문 추출"
        )
        db_history.insert(0, new_hist)
        
        return jsonify(response.model_dump())
    except Exception as e:
        return jsonify({"detail": f"Interview question generation failed: {str(e)}"}), 500

@app.route("/api/analyze/cover-letter-compare", methods=["POST"])
async def api_analyze_cover_letter_compare():
    try:
        data = request.get_json()
        payload = CoverLetterCompareRequest.model_validate(data)
        response = await compare_cover_letters(payload.original_text, payload.improved_text)
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="cover-letter",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"자소서 비교 분석 완료: 개선된 표현 {len(response.improved_expressions)}개"
        )
        db_history.insert(0, new_hist)
        
        return jsonify(response.model_dump())
    except Exception as e:
        return jsonify({"detail": f"Cover letter comparison failed: {str(e)}"}), 500

@app.route("/api/github/preview", methods=["GET"])
async def api_github_preview():
    username = request.args.get("username", "").strip()

    if not username:
        return jsonify({"error": "username 파라미터가 필요합니다."}), 400

    github_result = await test_github(username)

    if github_result.get("error"):
        status = 404 if "찾을 수 없습니다" in github_result["error"] else 400
        return jsonify({"error": github_result["error"]}), status

    skill_result = await infer_skills(
        username=username,
        languages=github_result["languages"],
        topics=github_result["topics"],
    )

    return jsonify({
        "username": username,
        "confirmed_skills": skill_result["confirmed"],
        "inferred_skills": skill_result["inferred"],
        "raw_languages": github_result["languages"],
    })


@app.route("/api/analyze/unified", methods=["POST"])
async def api_analyze_unified():
    try:
        from models import UnifiedGithubPart, UnifiedResumePart, UnifiedGapPart
        data = request.get_json()
        payload = UnifiedAnalysisRequest.model_validate(data)

        # Use URLs provided by user
        job_urls = payload.job_urls if payload.job_urls else ["https://toss.im/career/job-detail/backend-developer"]

        # 1. Run GitHub analysis
        github_res = await analyze_github([payload.github_url], job_urls)

        # 2. Run Resume verification matching
        resume_res = await match_resume_github(
            payload.resume_text,
            None,
            "kimcoding-dev",
            github_res.strong_skills
        )

        # 3. Run Gap analysis
        gap_res = await analyze_gap([payload.github_url], payload.resume_text, job_urls)
        
        # Build pieces
        readme_q = github_res.repo_details[0].readme_status if github_res.repo_details else "우수"
        completeness = "매우 우수" if github_res.overall_job_fit >= 80 else "보통 (클린 아키텍처 패턴은 우수하나 리드미 설명 보완 필요)"
        
        github_part = UnifiedGithubPart(
            repo_count=len(github_res.repo_details),
            tech_stack=github_res.strong_skills,
            readme_quality=readme_q,
            project_completeness=completeness,
            readme_suggestions=github_res.readme_suggestions,
            repo_details=github_res.repo_details
        )
        
        verified_count = len(resume_res.verified_skills)
        total_resume = len(resume_res.resume_skills)
        matching_pct = int((verified_count / max(total_resume, 1)) * 100)
        
        resume_part = UnifiedResumePart(
            resume_quality="매우 우수" if matching_pct >= 85 else "보통 (일부 기재 기술에 대한 GitHub 코드 증빙 보완 필요)",
            tech_stack_matching=matching_pct,
            verified_skills=resume_res.verified_skills,
            unverified_skills=resume_res.unverified_skills,
            missing_skills=github_res.weak_skills
        )
        
        learning_roadmap = [
            f"1단계: 부족한 기술인 {github_res.weak_skills[0]}의 기본 동작 원리를 실무 미니 예제로 구현" if len(github_res.weak_skills) > 0 else "1단계: Docker 컨테이너 및 인프라 구조 개념 학습",
            f"2단계: {github_res.weak_skills[1] if len(github_res.weak_skills) > 1 else 'AWS 클라우드'}를 활용한 분산 환경 무중단 배포 적용" if len(github_res.weak_skills) > 0 else "2단계: AWS ECS 및 RDS 인프라 배포 자동화 파이프라인 연동",
            "3단계: 아키텍처 다이어그램 설계와 상세 트러블슈팅 로그를 깃허브 README에 명시화"
        ]
        
        gap_part = UnifiedGapPart(
            missing_technologies=github_res.weak_skills,
            learning_roadmap=learning_roadmap
        )
        
        overall_score = int((github_res.overall_job_fit + matching_pct) / 2)
        
        response = UnifiedAnalysisResponse(
            overall_score=overall_score,
            portfolio_rating=github_res.portfolio_rating,
            github_analysis=github_part,
            resume_analysis=resume_part,
            skill_gap=gap_part,
            recommended_projects=gap_res.recommended_projects
        )
        
        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="gap",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"종합 커리어 진단 완료: 점수 {overall_score}점, A+ 등급"
        )
        db_history.insert(0, new_hist)
        
        return jsonify(response.model_dump())
    except Exception as e:
        return jsonify({"detail": f"Unified career analysis failed: {str(e)}"}), 500

# --- Profile and History Session endpoints ---

@app.route("/api/profile", methods=["GET"])
async def get_profile():
    return jsonify(db_profile.model_dump())

@app.route("/api/profile", methods=["POST"])
async def update_profile():
    global db_profile
    try:
        data = request.get_json(force=True, silent=True)
        if data is None:
            return jsonify({"detail": "Invalid or missing JSON body"}), 400
        db_profile = UserProfile.model_validate(data)
        return jsonify(db_profile.model_dump())
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"detail": f"Profile update failed: {str(e)}"}), 400

@app.route("/api/history", methods=["GET"])
async def get_history():
    return jsonify([item.model_dump() for item in db_history])

@app.route("/api/history/<id>", methods=["DELETE"])
async def delete_history_item(id):
    global db_history
    db_history = [item for item in db_history if item.id != id]
    return jsonify({"status": "success", "message": "History item deleted"})

if __name__ == '__main__':
    app.run(port=8000, debug=True)
