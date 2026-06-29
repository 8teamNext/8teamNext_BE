"""
leancageAnalysis 테스트 라우터

등록 방법 (app.py):
    from services.leancageAnalysisTest import leancage_test_bp
    app.register_blueprint(leancage_test_bp)

엔드포인트:
    POST /api/leancage/analyze       — URL 파싱 후 분석 (실제 사용 흐름)
    POST /api/leancage/analyze/mock  — 파싱된 jobs 직접 전달 (URL 없이 단위 테스트)
    GET  /api/leancage/health        — 서비스 상태 확인
"""

import os
import asyncio
from flask import Blueprint, request, jsonify
from flasgger import swag_from

from services.leancageAnalysis import leancage_analysis
from services.parsers.parser_router import parse_job

leancage_test_bp = Blueprint("leancage_test", __name__)

_SW = lambda f: os.path.join(os.path.dirname(__file__), '..', 'swagger', f)


# ─── GET /api/leancage/health ─────────────────────────────────────────────────

@leancage_test_bp.route("/api/leancage/health", methods=["GET"])
@swag_from(_SW('leancage_health.yml'))
def leancage_health():
    return jsonify({"status": "ok", "service": "leancage"})


# ─── POST /api/leancage/analyze ───────────────────────────────────────────────

@leancage_test_bp.route("/api/leancage/analyze", methods=["POST"])
@swag_from(_SW('leancage_analyze.yml'))
async def leancage_analyze():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body가 필요합니다."}), 400

    resume_text: str = data.get("resume_text", "").strip()
    job_urls: list = data.get("job_urls", [])

    if not resume_text:
        return jsonify({"error": "resume_text가 비어 있습니다."}), 400
    if not job_urls:
        return jsonify({"error": "job_urls가 비어 있습니다."}), 400
    if len(job_urls) > 5:
        return jsonify({"error": "job_urls는 최대 5개까지 입력 가능합니다."}), 400

    # 공고 URL 병렬 파싱
    parsed_jobs = [
        job.to_dict()
        for job in await asyncio.gather(*[parse_job(url) for url in job_urls])
    ]

    # 파싱 결과 요약 출력 (서버 로그용)
    for job in parsed_jobs:
        status = f"오류: {job['error']}" if job.get("error") else f"{job['company']} · {job['title']} · 기술 {len(job['tech_stack'])}개"
        print(f"  [parse] {job['url'][:60]}... → {status}")

    result = await leancage_analysis(resume_text, parsed_jobs)
    return jsonify(result)


# ─── POST /api/leancage/analyze/mock ─────────────────────────────────────────

@leancage_test_bp.route("/api/leancage/analyze/mock", methods=["POST"])
@swag_from(_SW('leancage_analyze_mock.yml'))
async def leancage_analyze_mock():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body가 필요합니다."}), 400

    resume_text: str = data.get("resume_text", "").strip()
    parsed_jobs: list = data.get("parsed_jobs", [])

    if not resume_text:
        return jsonify({"error": "resume_text가 비어 있습니다."}), 400
    if not parsed_jobs:
        return jsonify({"error": "parsed_jobs가 비어 있습니다."}), 400

    result = await leancage_analysis(resume_text, parsed_jobs)
    return jsonify(result)
