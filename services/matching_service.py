"""
매칭 서비스
- GitHub 기술스택 vs 채용공고 기술스택 비교
- 공고별 confirmed / inferred 점수 계산
- positions는 그대로 전달 (매칭은 전체 tech_stack 기준)
"""


def _normalize(skill: str) -> str:
    """대소문자, 공백 정규화"""
    return skill.strip().lower()


def match_single(
    confirmed_skills: list[str],
    inferred_skills: list[str],
    jd_tech_stack: list[str],
    url_index: int,
    title: str = "",
    company: str = "",
    job_type: str = "",
    positions: list[dict] = [],
) -> dict:
    """
    단일 공고와 GitHub 기술스택 매칭

    반환:
    {
        "url_index": 0,
        "title": "...",
        "company": "...",
        "job_type": "...",
        "positions": [...],   ← 세부직무 그대로 전달
        "jd_total": 3,
        "confirmed_score": 66.7,
        "inferred_score": 33.3,
        "confirmed_matched": ["TypeScript"],
        "inferred_matched": ["React"],
        "missing": ["Docker"],
        "extra_confirmed": ["JavaScript"],
    }
    """
    jd_normalized = {_normalize(s) for s in jd_tech_stack}
    confirmed_normalized = {_normalize(s): s for s in confirmed_skills}
    inferred_normalized = {_normalize(s): s for s in inferred_skills}

    jd_total = len(jd_normalized)

    if jd_total == 0:
        return {
            "url_index": url_index,
            "title": title,
            "company": company,
            "job_type": job_type,
            "positions": positions,
            "jd_total": 0,
            "confirmed_score": 0.0,
            "inferred_score": 0.0,
            "confirmed_matched": [],
            "inferred_matched": [],
            "missing": list(jd_tech_stack),
            "extra_confirmed": list(confirmed_skills),
        }

    # confirmed 매칭
    confirmed_matched = [
        confirmed_normalized[n]
        for n in confirmed_normalized
        if n in jd_normalized
    ]

    # inferred 매칭 (confirmed 중복 제거)
    confirmed_matched_normalized = {_normalize(s) for s in confirmed_matched}
    inferred_matched = [
        inferred_normalized[n]
        for n in inferred_normalized
        if n in jd_normalized and n not in confirmed_matched_normalized
    ]

    # 부족한 기술 (JD에 있는데 내가 없는 것)
    all_my_normalized = set(confirmed_normalized.keys()) | set(inferred_normalized.keys())
    missing = [
        s for s in jd_tech_stack
        if _normalize(s) not in all_my_normalized
    ]

    # 추가 기술 (내가 있는데 JD에 없는 것 - confirmed만)
    extra_confirmed = [
        s for s in confirmed_skills
        if _normalize(s) not in jd_normalized
    ]

    # 점수 계산
    confirmed_score = round(len(confirmed_matched) / jd_total * 100, 1)
    inferred_score = round(len(inferred_matched) / jd_total * 100, 1)

    return {
        "url_index": url_index,
        "title": title,
        "company": company,
        "job_type": job_type,
        "positions": positions,
        "jd_total": jd_total,
        "confirmed_score": confirmed_score,
        "inferred_score": inferred_score,
        "confirmed_matched": confirmed_matched,
        "inferred_matched": inferred_matched,
        "missing": missing,
        "extra_confirmed": extra_confirmed,
    }


def match_all(
    confirmed_skills: list[str],
    inferred_skills: list[str],
    crawl_results: list[dict],
) -> list[dict]:
    """
    전체 공고 매칭

    crawl_results: crawler.py 응답의 results 배열
    반환: 공고별 매칭 결과 배열
    """
    matching = []

    for result in crawl_results:
        if result.get("status") == "failed":
            matching.append({
                "url_index": result["url_index"],
                "status": "failed",
                "error": result.get("error", "크롤링 실패"),
            })
            continue

        matched = match_single(
            confirmed_skills=confirmed_skills,
            inferred_skills=inferred_skills,
            jd_tech_stack=result.get("tech_stack", []),
            url_index=result["url_index"],
            title=result.get("title", ""),
            company=result.get("company", ""),
            job_type=result.get("job_type", ""),
            positions=result.get("positions", []),  # 세부직무 전달
        )
        matched["status"] = "success"
        matching.append(matched)

    return matching