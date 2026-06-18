"""
채용공고 크롤링 서비스
- POST /api/crawl 라우트에서 호출
- URL 1~5개를 받아 비동기 병렬 파싱 후 결과 반환
- 원문/URL 로그 저장 없음
"""

import asyncio
from flask import Blueprint, request, jsonify
from services.parsers.parser_router import parse_job

crawler_bp = Blueprint("crawler", __name__)


async def _parse_with_index(index: int, url: str) -> dict:
    """단일 URL 파싱 후 url_index 포함한 결과 반환."""
    try:
        result = await parse_job(url)
        d = result.to_dict()

        if d.get("error"):
            return {
                "url_index": index,
                "status": "failed",
                "error": d["error"],
            }

        return {
            "url_index": index,
            "status": "success",
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "job_type": d.get("job_type", ""),
            "tech_stack": d.get("tech_stack", []),
            "tasks": d.get("tasks", []),
        }

    except Exception as e:
        return {
            "url_index": index,
            "status": "failed",
            "error": f"파싱 중 오류 발생: {str(e)}",
        }


@crawler_bp.route("/crawl", methods=["POST"])
async def crawl():
    data = request.get_json(silent=True)

    # 요청 검증
    if not data or "urls" not in data:
        return jsonify({"error": "urls 필드가 필요합니다."}), 400

    urls = data["urls"]

    if not isinstance(urls, list) or len(urls) == 0:
        return jsonify({"error": "urls는 1개 이상의 배열이어야 합니다."}), 400

    if len(urls) > 5:
        return jsonify({"error": "urls는 최대 5개까지 입력 가능합니다."}), 400

    # URL 형식 기본 검증
    for url in urls:
        if not isinstance(url, str) or not url.startswith("http"):
            return jsonify({"error": f"올바르지 않은 URL 형식입니다: {url}"}), 400

    # 병렬 파싱
    tasks = [_parse_with_index(i, url) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks)

    return jsonify({"results": list(results)})