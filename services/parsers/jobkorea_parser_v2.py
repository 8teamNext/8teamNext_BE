import re
import requests
from bs4 import BeautifulSoup
from typing import Optional

from .base import (
    JobInfo,
    extract_techs_from_text,
    detect_job_type,
    normalize_tech,
)
import json

# 요청 설정 
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.jobkorea.co.kr/",
}

# 담당업무 섹션 헤딩 키워드
_TASK_KEYWORDS = ["담당업무", "주요업무", "하는 일", "업무내용", "담당 업무", "주요 업무"]

# 자격/기술 섹션 헤딩 키워드
_SKILL_KEYWORDS = ["기술스택", "기술 스택", "자격요건", "필요역량", "우대사항", "요구사항",
                   "스킬", "skill", "requirement", "qualification", "tech"]


# HTML 파싱 로직 
def _parse_html(html: str, url: str) -> JobInfo:
    info = JobInfo(url=url)

    soup = BeautifulSoup(html, "html.parser")

    # JSON-LD 먼저 추출 (script 제거 전에)
    json_ld = soup.select_one('script[type="application/ld+json"]')
    if json_ld and json_ld.string:
        try:
            ld_data = json.loads(json_ld.string)
            info.title = ld_data.get("title", "")
            info.company = ld_data.get("hiringOrganization", {}).get("name", "")
        except Exception:
            pass

    # OCR URL 탐색 (script 제거 전 원본 html에서)
    ocr_url: str | None = None
    m = re.search(r'https://[^"\']+OCR\.html[^"\']*', html)
    if m:
        ocr_url = m.group(0).replace("\\u0026", "&")
    else:
        for iframe in soup.select("iframe[src]"):
            src = iframe.get("src", "")
            if "OCR" in src:
                ocr_url = src
                break

    # 노이즈 태그 제거
    for tag in soup(["script", "style", "nav", "header", "footer", "iframe", "noscript"]):
        tag.decompose()

    # 공고 본문 컨테이너 우선 탐색
    _BODY_SELECTORS = [
        ".artReadBody",
        ".artReadBodyRead",
        ".jobReadBody",
        ".recruit-read",
        ".dev-content",
        ".cont-wrap",
        "#contents",
        "main",
    ]
    body_el = next((soup.select_one(s) for s in _BODY_SELECTORS if soup.select_one(s)), None)
    candidate = (body_el or soup.body or soup).get_text(separator="\n", strip=True)
    # body_el가 너무 좁으면 body 전체 사용
    if body_el and len(candidate) < 1000 and soup.body:
        candidate = soup.body.get_text(separator="\n", strip=True)
    info.raw_text = candidate

    # OCR HTML 추가 요청 (실제 JD 본문)
    if ocr_url:
        try:
            res = requests.get(ocr_url, headers=_HEADERS, timeout=10)
            if res.status_code == 200:
                ocr_soup = BeautifulSoup(res.text, "html.parser")
                for tag in ocr_soup(["script", "style"]):
                    tag.decompose()
                info.raw_text += "\n" + ocr_soup.get_text(separator="\n", strip=True)
        except Exception as e:
            print("OCR 다운로드 실패:", e)

    # 잡코리아 공고 제목: .tit-job h1 또는 .artReadSub .tit
    if not info.title:
        for sel in [
        "main h1",
        "h1",
        ".tit-job h1",
        ".tit-job",
        "h1.tit",
    ]:
            el = soup.select_one(sel)

        if el and el.get_text(strip=True):
            info.title = el.get_text(strip=True)
            # break

    #  회사명
    if not info.company:
        for sel in [
        "main h2",
        "h2",
        ".coname a",
        ".name-company",
        ".corp-name a",
    ]:
            el = soup.select_one(sel)

        if el and el.get_text(strip=True):
            info.company = el.get_text(strip=True)
    #break

    # 구분 (신입/경력/무관) 
    # 잡코리아는 .tbList 테이블 안에 채용 조건 정보가 있음
    recruit_table = soup.select_one(".tbList") or soup.select_one(".info-list")
    if recruit_table:
        info.job_type = detect_job_type(recruit_table.get_text())
    if not info.job_type:
        info.job_type = detect_job_type(info.raw_text)

    # 본문 섹션 파싱 ─
    # 잡코리아 공고 본문 구조:
    #   .artReadBody > .artReadBodyRead > 각 섹션
    #   또는 .jobReadBody > dl > dt(헤딩) + dd(내용)
    tasks_raw: list[str] = []
    skills_raw: list[str] = []

    # 방법 1: dl/dt/dd 구조 (잡코리아 구형 레이아웃)
    dl_sections = soup.select(".artReadBody dl, .jobReadBody dl, .recruit-read dl")
    for dl in dl_sections:
        dt = dl.select_one("dt")
        dd = dl.select_one("dd")
        if not dt or not dd:
            continue
        heading = dt.get_text(strip=True)
        lines = [l.strip() for l in dd.get_text(separator="\n").splitlines() if l.strip()]

        if any(kw in heading for kw in _TASK_KEYWORDS):
            tasks_raw = lines
        elif any(kw.lower() in heading.lower() for kw in _SKILL_KEYWORDS):
            skills_raw.extend(lines)

    # 방법 2: 섹션 헤딩 기반 (잡코리아 신형 레이아웃)
    if not tasks_raw and not skills_raw:
        # .recruitInfo, .dev-content 등 컨테이너 내 헤딩 탐색
        body = (
            soup.select_one(".artReadBodyRead")
            or soup.select_one(".jobReadBody")
            or soup.select_one(".dev-content")
            or soup.select_one(".cont-wrap")
            or soup.body
        )
        if body:
            # h3, h4, strong 등 헤딩 역할 태그 탐색
            headings = body.find_all(["h3", "h4", "h5", "strong", "b"],
                                      string=lambda t: t and len(t.strip()) < 30)
            for hel in headings:
                heading = hel.get_text(strip=True)
                # 헤딩 다음 형제 또는 부모의 텍스트 수집
                content_el = hel.find_next_sibling() or hel.parent
                if not content_el:
                    continue
                lines = [l.strip() for l in
                         content_el.get_text(separator="\n").splitlines()
                         if l.strip() and l.strip() != heading]

                if any(kw in heading for kw in _TASK_KEYWORDS):
                    tasks_raw = lines
                elif any(kw.lower() in heading.lower() for kw in _SKILL_KEYWORDS):
                    skills_raw.extend(lines)

    info.tasks = tasks_raw

    # 스킬 태그 CSS 셀렉터 기반 추출 (잡코리아 신형 레이아웃)
    _SKILL_TAG_SELECTORS = [
        ".skill-wrap .skill",
        ".skill-list li",
        ".chip-list .chip",
        ".tag-list .tag",
        "[class*='skill'] li",
        "[class*='Skill'] li",
        ".stackList li",
        ".tech-stack li",
    ]
    tag_skills: list[str] = []
    for sel in _SKILL_TAG_SELECTORS:
        els = soup.select(sel)
        if els:
            tag_skills = [e.get_text(strip=True) for e in els if e.get_text(strip=True)]
            break

    # 헤딩 기반 skills_raw + 태그 기반 tag_skills 합산 (중복 제거)
    combined = list(dict.fromkeys(skills_raw + tag_skills))
    info.skills = combined

    info.tech_stack = extract_techs_from_text(info.raw_text)

# ── 기술스택 추출 ──────────────────────────────────────────────────────
    # tech_source = " ".join(skills_raw)

    # if ocr_text:
    #     tech_source += "\n" + ocr_text

    # if not tech_source.strip():
    #     tech_source = info.raw_text

# 무조건 실행
    
    # info.tech_stack = extract_techs_from_text(tech_source)

    # parsed = extract_techs_from_text(tech_source)

    # print("parsed =", parsed)

    # info.tech_stack = parsed

    print("assigned =", info.tech_stack)

    print("info.tech_stack =", info.tech_stack)

    print("title =", info.title)
    print("company =", info.company)
    print("job_type =", info.job_type)
    print("INFO ID =", id(info))
    print("RETURN INFO =", info.tech_stack)

    return info




# ── requests 기반 파싱 ────────────────────────────────────────────────────
def _fetch_with_requests(url: str) -> Optional[str]:
    """HTML 반환, 실패 시 None."""
    session = requests.Session()
    try:
        # 쿠키 획득을 위해 메인 페이지 선방문
        session.get("https://www.jobkorea.co.kr/", headers=_HEADERS, timeout=8)
        res = session.get(url, headers=_HEADERS, timeout=12)
        if res.status_code == 200 and len(res.text) > 1000:
            return res.text
        return None
    except Exception:
        return None


# ── Playwright 폴백 ───────────────────────────────────────────────────────
# async def _fetch_with_playwright(url: str) -> Optional[str]:
#     """requests 실패 시 Playwright headless로 재시도."""
#     try:
#         from playwright.async_api import async_playwright
#     except ImportError:
#         return None

#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)

#         context = await browser.new_context(
#             user_agent=_HEADERS["User-Agent"],
#             locale="ko-KR",
#         )

#         page = await context.new_page()

#         try:
#             await page.goto(
#                 url,
#                 wait_until="networkidle",
#                 timeout=20_000
#             )

#             # JS 렌더링 추가 대기
#             await page.wait_for_timeout(3000)


#         finally:
#             await browser.close()
async def _fetch_with_playwright(url: str) -> Optional[str]:
    """requests 실패 시 Playwright headless로 재시도."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            locale="ko-KR",
        )

        page = await context.new_page()

        try:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=20_000
            )

            # JS 렌더링 대기
            await page.wait_for_timeout(3000)

            html = await page.content()

            # 추가
            # with open(
            #     "playwright_debug.html",
            #     "w",
            #     encoding="utf-8"
            # ) as f:
            #     f.write(html)

            # print("playwright_debug.html 생성 완료")

            return html

        except Exception as e:
            print("Playwright 오류:", e)
            return None

        finally:
            await browser.close()

#  공개 인터페이스
def parse_jobkorea_sync(url: str) -> JobInfo:
    """동기 버전 (requests 전용, Playwright 폴백 없음)."""
    info = JobInfo(url=url)
    html = _fetch_with_requests(url)
    if not html:
        info.error = "requests 요청 실패 (403 또는 타임아웃). parse_jobkorea() 비동기 버전을 사용하세요."
        return info
    return _parse_html(html, url)


async def parse_jobkorea(url: str) -> JobInfo:
    """
    비동기 버전. requests 우선 시도 → 실패 시 Playwright 폴백.
    ENABLE_PLAYWRIGHT=false 환경변수로 Playwright를 비활성화할 수 있습니다 (저사양 서버용).
    """
    import os
    info = JobInfo(url=url)

    # 1차: requests (빠름, 가벼움 — ~수 MB)
    html = _fetch_with_requests(url)

    # 2차: Playwright 폴백 (메모리 300~800MB 필요 — 환경변수로 제어)
    if not html:
        playwright_enabled = os.getenv("ENABLE_PLAYWRIGHT", "true").lower() != "false"
        if playwright_enabled:
            html = await _fetch_with_playwright(url)
        if not html:
            info.error = "페이지 로드 실패 (requests + Playwright 모두 실패)"
            return info

    return _parse_html(html, url)


# 실행 예시
if __name__ == "__main__":
    import asyncio, json, sys
#공고url
    url = sys.argv[1] if len(sys.argv) > 1 else (
        "https://www.jobkorea.co.kr/Recruit/GI_Read/49354072?Oem_Code=C1&rPageCode=TL&sc=416"
    )

    async def main():
        result = await parse_jobkorea(url)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    asyncio.run(main())