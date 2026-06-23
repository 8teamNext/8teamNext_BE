import re
import requests
import json
from bs4 import BeautifulSoup
from typing import Optional

from .base import (
    JobInfo,
    extract_techs_from_text,
    detect_job_type,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

_TASK_KEYWORDS = ["담당업무", "주요업무", "하는 일", "업무내용"]
_SKILL_KEYWORDS = ["기술스택", "기술 스택", "자격요건", "필요역량", "우대사항", "skill", "tech"]



# IFRAME HTML
def _fetch_iframe_html(main_html: str) -> Optional[str]:
    """
    메인 페이지 HTML에서 iframe src 추출 후
    iframe 내용을 requests로 가져옴
    """
    soup = BeautifulSoup(main_html, "html.parser")

    # iframe[src*='GI_Read_Comt_Ifrm'] 탐색
    iframe = soup.select_one("iframe[src*='GI_Read_Comt_Ifrm']")
    if not iframe:
        return None

    iframe_src = iframe.get("src", "")
    if not iframe_src:
        return None

    # 상대경로면 절대경로로
    if iframe_src.startswith("/"):
        iframe_url = "https://www.jobkorea.co.kr" + iframe_src
    else:
        iframe_url = iframe_src

    try:
        session = requests.Session()
        session.get("https://www.jobkorea.co.kr/", headers=_HEADERS, timeout=8)
        res = session.get(iframe_url, headers=_HEADERS, timeout=12)
        if res.status_code == 200 and len(res.text) > 500:
            return res.text
    except Exception as e:
        print("iframe fetch 실패:", e)

    return None

# HTML PARSE

def _parse_html(html: str, url: str) -> JobInfo:
    soup = BeautifulSoup(html, "html.parser")
    info = JobInfo(url=url)

    info.raw_text = soup.get_text(separator=" ", strip=True)
    recruitment_items = soup.select(".recruitment-item")
    print(f"recruitment-item 개수: {len(recruitment_items)}")
    for i, item in enumerate(recruitment_items):
        print(f"\n--- ITEM {i} ---")
        print(item.get_text(strip=True)[:500])

  
    # JSON

    json_ld = soup.select_one('script[type="application/ld+json"]')
    if json_ld and json_ld.string:
        try:
            data = json.loads(json_ld.string)
            info.title = data.get("title", "")
            info.company = data.get("hiringOrganization", {}).get("name", "")
        except:
            pass


    # OCR URL

    ocr_match = re.search(r'https://[^"]+OCR\.html[^"]*', html)
    ocr_text = ""

    if ocr_match:
        ocr_url = ocr_match.group(0).replace("\\u0026", "&")
        try:
            res = requests.get(ocr_url, headers=_HEADERS, timeout=10)
            if res.status_code == 200:
                ocr_soup = BeautifulSoup(res.text, "html.parser")
                ocr_text = ocr_soup.get_text(separator="\n", strip=True)
                info.raw_text += "\n" + ocr_text
        except Exception as e:
            print("OCR 실패:", e)


    # title fallback

    if not info.title:
        for sel in ["main h1", "h1", ".tit-job h1", ".tit-job", "h1.tit"]:
            el = soup.select_one(sel)
            if el:
                info.title = el.get_text(strip=True)
                break


    # company fallback

    if not info.company:
        for sel in [".coname a", ".name-company", ".corp-name a", "h2", "main h2"]:
            el = soup.select_one(sel)
            if el:
                info.company = el.get_text(strip=True)
                break


    # job type

    recruit_table = soup.select_one(".tbList") or soup.select_one(".info-list")
    if recruit_table:
        info.job_type = detect_job_type(recruit_table.get_text())
    else:
        info.job_type = detect_job_type(info.raw_text)

    # 채용상세 parsing

    tasks_raw = []
    skills_raw = []

    # 1) dl 구조
    dl_sections = soup.select("dl")
    for dl in dl_sections:
        dt = dl.select_one("dt")
        dd = dl.select_one("dd")
        if not dt or not dd:
            continue

        heading = dt.get_text(strip=True)
        lines = [x.strip() for x in dd.get_text("\n").splitlines() if x.strip()]

        if any(k in heading for k in _TASK_KEYWORDS):
            tasks_raw = lines
        elif any(k.lower() in heading.lower() for k in _SKILL_KEYWORDS):
            skills_raw.extend(lines)

    # 2) recruitment-item 구조
    if not tasks_raw and not skills_raw:
        recruitment_items = soup.select(".recruitment-item")

        for item in recruitment_items:
            text = item.get_text("\n", strip=True)

            if any(k in text for k in _TASK_KEYWORDS):
                tasks_raw.extend(text.splitlines())

            if any(k in text for k in _SKILL_KEYWORDS):
                skills_raw.extend(text.splitlines())

    info.tasks = tasks_raw


    # tech stack

    tech_source = " ".join(skills_raw)

    if ocr_text:
        tech_source += "\n" + ocr_text

    if not tech_source.strip():
        tech_source = info.raw_text

    info.tech_stack = extract_techs_from_text(tech_source)

    return info



# requests

def _fetch_with_requests(url: str) -> Optional[str]:
    try:
        session = requests.Session()
        session.get("https://www.jobkorea.co.kr/", headers=_HEADERS, timeout=8)
        res = session.get(url, headers=_HEADERS, timeout=12)

        if res.status_code == 200 and len(res.text) > 1000:
            return res.text
    except:
        pass
    return None



# playwright

async def _fetch_with_playwright(url: str) -> Optional[str]:
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
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(4000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            try:
                await page.wait_for_selector("main", timeout=10000)
            except:
                pass

            html = await page.content()
            return html

        except Exception as e:
            print("Playwright 오류:", e)
            return None

        finally:
            await browser.close()


# ASYNC MAIN

async def parse_jobkorea(url: str) -> JobInfo:
    info = JobInfo(url=url)

    # 1. Playwright로 메인 페이지 가져오기
    html = await _fetch_with_playwright(url)

    if not html:
        html = _fetch_with_requests(url)

    if not html:
        info.error = "페이지 로드 실패"
        return info

    # 2. 메인 페이지에서 JSON-LD로 title/company 추출
    #    + iframe URL 추출 후 iframe 내용으로 파싱
    iframe_html = _fetch_iframe_html(html)

    if iframe_html:
        # iframe 내용으로 recruitment-item 파싱
        result = _parse_html(iframe_html, url)

        # title/company는 메인 페이지 JSON가 더 정확하므로 덮어쓰기
        main_soup = BeautifulSoup(html, "html.parser")
        json_ld = main_soup.select_one('script[type="application/ld+json"]')
        if json_ld and json_ld.string:
            try:
                data = json.loads(json_ld.string)
                title = data.get("title", "")
                company = data.get("hiringOrganization", {}).get("name", "")
                if title:
                    result.title = title
                if company:
                    result.company = company
            except:
                pass

        # job_type도 메인 페이지에서 다시 추출
        if not result.job_type:
            result.job_type = detect_job_type(main_soup.get_text())

        return result

    # iframe 없으면 메인 페이지로 파싱 (기존 방식)
    return _parse_html(html, url)



# TEST 실행(아래 명령어)
# python -m services.parsers.jobkorea_parser "https://www.jobkorea.co.kr/Recruit/GI_Read/49416174"

if __name__ == "__main__":
    import asyncio, sys

    url = sys.argv[1]

    async def main():
        result = await parse_jobkorea(url)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    asyncio.run(main())