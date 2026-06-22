import asyncio
import uuid
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from typing import List, Dict, Any
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from services.crawler import crawler_bp 
from services.github_analyzer import analyze_github
from services.github_service import test_github
from services.llm_service import infer_skills


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
from services.leancageAnalysisTest import leancage_test_bp

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

app.register_blueprint(leancage_test_bp)

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

        from services.github_analyzer import extract_username, LANGUAGE_TO_SKILL
        job_urls = payload.job_urls if payload.job_urls else ["https://toss.im/career/job-detail/backend-developer"]
        username = extract_username(payload.github_url)
        print(f"\n=== 분석 시작 ===")
        print(f"github_url: {payload.github_url}")
        print(f"username: {username}")
        print(f"resume 앞 100자: {payload.resume_text[:100]}")

        from services.llm_analyzer import extract_skills_from_resume, generate_analysis_comment

        # 1. GitHub 분석 + Gap 분석 + LLM 이력서 기술 추출 병렬 실행
        github_res, gap_res, llm_resume_skills = await asyncio.gather(
            analyze_github([payload.github_url], job_urls),
            analyze_gap([payload.github_url], payload.resume_text, job_urls),
            extract_skills_from_resume(payload.resume_text),
        )
        print(f"github strong_skills: {github_res.strong_skills}")
        print(f"github repo_details 수: {len(github_res.repo_details)}")
        print(f"active_weeks: {github_res.active_weeks}, total_commits: {github_res.total_commits}")
        print(f"LLM 이력서 기술 추출: {llm_resume_skills}")

        # 2. 이력서-GitHub 기술 대조 (LLM 추출 기술 우선, 없으면 키워드 매칭 폴백)
        resume_res = await match_resume_github(
            payload.resume_text,
            None,
            username,
            github_res.strong_skills,
            llm_skills=llm_resume_skills if llm_resume_skills else None,
        )

        # GitHub 파트 조립
        total_commits = sum(r.commit_count for r in github_res.repo_details)
        readme_statuses = [r.readme_status for r in github_res.repo_details]
        good_count = sum(1 for s in readme_statuses if s == "우수")
        readme_q = "우수" if good_count >= len(readme_statuses) * 0.6 else "보통" if good_count > 0 else "미흡"
        completeness = "매우 우수" if github_res.overall_job_fit >= 80 else "보통"

        total_commits = sum(r.commit_count for r in github_res.repo_details)
        active_weeks = github_res.active_weeks
        readme_statuses = [r.readme_status for r in github_res.repo_details]
        good_count = sum(1 for s in readme_statuses if s == "우수")
        readme_q = "우수" if good_count >= max(len(readme_statuses) * 0.6, 1) else "보통" if good_count > 0 else "미흡"
        completeness = "매우 우수" if github_res.overall_job_fit >= 80 else "보통"

        github_part = UnifiedGithubPart(
            repo_count=len(github_res.repo_details),
            total_commits=total_commits,
            tech_stack=github_res.strong_skills,
            readme_quality=readme_q,
            project_completeness=completeness,
            readme_suggestions=github_res.readme_suggestions,
            repo_details=github_res.repo_details,
        )

        verified_count = len(resume_res.verified_skills)
        total_resume = len(resume_res.resume_skills)
        matching_pct = int(verified_count / max(total_resume, 1) * 100)

        resume_quality_comment = (
            f"이력서 기재 {total_resume}개 기술 중 {verified_count}개({matching_pct}%)가 GitHub 실제 코드에서 검증되었습니다."
            if total_resume > 0
            else "이력서에서 기술 스택을 추출하지 못했습니다."
        )

        resume_part = UnifiedResumePart(
            resume_quality=resume_quality_comment,
            tech_stack_matching=matching_pct,
            verified_skills=resume_res.verified_skills,
            unverified_skills=resume_res.unverified_skills,
            missing_skills=github_res.weak_skills,
        )

        # 로드맵: 미보유 기술 기반으로 동적 생성
        missing = github_res.weak_skills
        learning_roadmap = []
        for i, skill in enumerate(missing[:3], 1):
            learning_roadmap.append(f"{i}단계: {skill} 기초 프로젝트를 직접 구현하고 GitHub에 커밋하여 포트폴리오에 증빙 추가")
        if not learning_roadmap:
            learning_roadmap = ["현재 기술 스택이 채용 요구 사항을 충족합니다. 심화 프로젝트로 깊이를 더하세요."]

        gap_part = UnifiedGapPart(
            missing_technologies=missing,
            learning_roadmap=learning_roadmap,
        )

        # ── 4개 지표 계산 ─────────────────────────────────────────────────────
        from services.text_utils import normalize_skill_set
        # 1. 기술스택 일치도: 이력서 기술 중 GitHub에서 증명된 비율 (이력서 기준)
        github_skill_set = normalize_skill_set(set(github_res.strong_skills))
        resume_skill_set = normalize_skill_set(set(resume_res.resume_skills))
        intersection = github_skill_set & resume_skill_set
        skill_match_pct = int(len(intersection) / max(len(resume_skill_set), 1) * 100)

        # 2. 깃 커밋: active_weeks, total_commits (github_res에서 가져옴)

        # 3. 레포 기술 커버리지: 이력서 기술이 사용된 레포 비율
        relevant_repos = sum(
            1 for r in github_res.repo_details
            if resume_skill_set & set(LANGUAGE_TO_SKILL.get(l, l) for l in r.languages)
        )
        repo_coverage_pct = int(relevant_repos / max(len(github_res.repo_details), 1) * 100)

        # 4. 공개 레포 수 (단순 카운트)
        repo_count = len(github_res.repo_details)

        # 전체 매칭 비율 (3개 항목 동일 가중치 33.3%씩)
        commit_activity_pct = min(int(active_weeks / 52 * 100), 100)
        overall_match_pct = int(
            (skill_match_pct + commit_activity_pct + repo_coverage_pct) / 3
        )

        print("\n+---------------------------------------------+")
        print("|        [resume-github analysis result]      |")
        print("+---------------------------------------------+")
        print(f"| resume skills ({len(resume_skill_set)}): {sorted(resume_skill_set)}")
        print(f"| github skills ({len(github_skill_set)}): {sorted(github_skill_set)}")
        print(f"| matched       ({len(intersection)}): {sorted(intersection)}")
        print("+---------------------------------------------+")
        print(f"| skill_match_pct    : {skill_match_pct:>3}%  ({len(intersection)}/{len(resume_skill_set)} skills proven)")
        print(f"| commit_activity_pct: {commit_activity_pct:>3}%  ({active_weeks}/52 weeks, {total_commits} commits)")
        print(f"| repo_coverage_pct  : {repo_coverage_pct:>3}%  ({relevant_repos}/{repo_count} repos)")
        print("+---------------------------------------------+")
        print(f"| service      : resume-github")
        print(f"| overall_score: {overall_match_pct}%")
        print("+---------------------------------------------+\n")

        # LLM 총평 생성
        ai_comment = await generate_analysis_comment(
            skill_match_pct=skill_match_pct,
            commit_activity_pct=commit_activity_pct,
            repo_coverage_pct=repo_coverage_pct,
            overall_score=overall_match_pct,
            matched_skills=sorted(intersection),
            unmatched_skills=sorted(resume_skill_set - github_skill_set),
            total_commits=total_commits,
            active_weeks=active_weeks,
            repo_count=repo_count,
        )
        print(f"  [LLM] 총평:\n{ai_comment}\n")

        # 종합 페이지 공통 포맷 조립
        from models import ComparisonResult, ComparisonRaw, MetricItem
        comparison_result = ComparisonResult(
            service="resume-github",
            overall_score=overall_match_pct,
            metrics=[
                MetricItem(
                    key="skill_match",
                    label="기술스택 일치도",
                    score=skill_match_pct,
                    detail=f"이력서 기술 {len(resume_skill_set)}개 중 {len(intersection)}개 증명"
                ),
                MetricItem(
                    key="commit_activity",
                    label="깃 커밋 활동",
                    score=commit_activity_pct,
                    detail=f"{active_weeks}/52주 · 총 {total_commits}커밋"
                ),
                MetricItem(
                    key="repo_coverage",
                    label="레포 기술 커버리지",
                    score=repo_coverage_pct,
                    detail=f"관련 레포 {relevant_repos}/{repo_count}개"
                ),
            ],
            raw=ComparisonRaw(
                active_weeks=active_weeks,
                total_commits=total_commits,
                repo_count=repo_count,
                matched_skills=sorted(intersection),
                unmatched_skills=sorted(resume_skill_set - github_skill_set),
            ),
            ai_comment=ai_comment,
        )

        response = UnifiedAnalysisResponse(
            portfolio_rating=github_res.portfolio_rating,
            overall_match_pct=overall_match_pct,
            skill_match_pct=skill_match_pct,
            active_weeks=active_weeks,
            total_commits=total_commits,
            repo_coverage_pct=repo_coverage_pct,
            repo_count=repo_count,
            github_analysis=github_part,
            resume_analysis=resume_part,
            skill_gap=gap_part,
            recommended_projects=gap_res.recommended_projects,
            comparison_result=comparison_result,
        )

        # Save to history
        new_hist = AnalysisHistoryItem(
            id=f"hist-{uuid.uuid4().hex[:6]}",
            type="gap",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=f"종합 커리어 진단: 기술일치도 {skill_match_pct}%, 활동 {active_weeks}주, 레포 {len(github_res.repo_details)}개"
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
