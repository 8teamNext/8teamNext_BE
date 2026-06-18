"""
채용공고 파서 라우터 — 잡코리아만 지원
"""

from .base import JobInfo
from .jobkorea_parser import parse_jobkorea

def _detect_platform(url: str) -> str:
    if "jobkorea.co.kr" in url:
        return "jobkorea"
    return "unsupported"


async def parse_job(url: str) -> JobInfo:
    if _detect_platform(url) != "jobkorea":
        return JobInfo(
            url=url,
            error="현재 잡코리아(jobkorea.co.kr) URL만 지원합니다."
        )
    return await parse_jobkorea(url)