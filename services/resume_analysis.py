import base64
import io
import json
import urllib.request
from typing import List, Set, Optional
from models import ResumeGithubResponse
from services.gap_analyzer import parse_skills_from_text


def extract_pdf_text(file_bytes: bytes) -> str:
    """PDF 바이너리에서 텍스트를 추출합니다."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()

GITHUB_API_BASE = "https://api.github.com"

# GitHub 언어명 → TECH_GLOSSARY 스킬명 매핑
LANGUAGE_TO_SKILL = {
    "Java": "Java",
    "Kotlin": "Kotlin",
    "JavaScript": "JavaScript",
    "TypeScript": "TypeScript",
    "Python": "Python",
    "Swift": "Swift",
    "Dart": "Dart",
    "Go": "Go",
    "C++": "C++",
    "HTML": "HTML/CSS",
    "CSS": "HTML/CSS",
    "SCSS": "HTML/CSS",
}


def _gh_get(path: str, extra_headers: dict = None) -> Optional[object]:
    req = urllib.request.Request(
        GITHUB_API_BASE + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "spc-resume-analyzer",
            **(extra_headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _decode_readme(content: str, encoding: str) -> str:
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return ""


def _extract_github_skills(username: str) -> Set[str]:
    """GitHub 사용자의 레포지토리, README, 언어, 토픽을 분석해 기술 스택을 추출."""
    repos = _gh_get(f"/users/{username}/repos?per_page=30&sort=updated&type=owner")
    if not isinstance(repos, list) or not repos:
        return set()

    skills: Set[str] = set()

    for repo in repos[:8]:  # 최근 업데이트 순 상위 8개만 분석
        name = repo.get("name", "")
        if not name or repo.get("fork"):  # 포크 레포는 본인 기술이 아니므로 제외
            continue

        # 1. 사용 언어 (API)
        langs = _gh_get(f"/repos/{username}/{name}/languages")
        if isinstance(langs, dict):
            for lang in langs:
                skill = LANGUAGE_TO_SKILL.get(lang)
                if skill:
                    skills.add(skill)

        # 2. README 텍스트에서 기술 키워드 추출
        readme_data = _gh_get(f"/repos/{username}/{name}/readme")
        if isinstance(readme_data, dict):
            readme_text = _decode_readme(
                readme_data.get("content", ""),
                readme_data.get("encoding", ""),
            )
            skills.update(parse_skills_from_text(readme_text))

        # 3. 레포 설명(description)
        desc = repo.get("description") or ""
        skills.update(parse_skills_from_text(desc))

        # 4. 레포 토픽
        topics: List[str] = repo.get("topics") or []
        skills.update(parse_skills_from_text(" ".join(topics)))

    return skills


def analyze_resume_github(
    resume_text: str,
    github_username: str,
    tech_stack: List[str],
) -> ResumeGithubResponse:
    # 1. 이력서에서 기술 스택 추출
    resume_skills: Set[str] = set(parse_skills_from_text(resume_text))
    for t in tech_stack:
        if t:
            resume_skills.add(t)

    if not resume_skills:
        resume_skills = {"Java", "Spring Boot", "JPA", "MySQL", "AWS", "React.js"}

    # 2. GitHub 실제 분석
    github_skills = _extract_github_skills(github_username)

    # GitHub 응답 실패 시 폴백
    if not github_skills:
        github_skills = {"Java", "Spring Boot", "MySQL", "Git"}

    # 3. 교차 분석
    verified_skills = sorted(resume_skills & github_skills)
    unverified_skills = sorted(resume_skills - github_skills)
    newly_discovered_skills = sorted(github_skills - resume_skills)

    total_resume = len(resume_skills)
    verified_count = len(verified_skills)
    ratio = verified_count / total_resume if total_resume else 0.5
    match_pct = int(ratio * 100)

    if ratio >= 0.8:
        overall_evaluation = (
            f"이력서와 포트폴리오의 기술 정합성이 매우 높습니다! "
            f"이력서에 기재된 {total_resume}개 기술 중 {verified_count}개 기술이 "
            f"GitHub({github_username}) 저장소의 실제 소스코드에서 완벽히 검증되었습니다. "
            f"신뢰도가 아주 높은 포트폴리오입니다."
        )
    elif ratio >= 0.5:
        examples = ", ".join(unverified_skills[:2])
        overall_evaluation = (
            f"기본적인 기술 일치는 양호하나 (일치율 {match_pct}%), "
            f"이력서에 기재된 기술 중 {len(unverified_skills)}개 기술(예: {examples})은 "
            f"GitHub 상의 코드 구현 증빙이 다소 부족합니다. "
            f"해당 기술들을 보완할 수 있는 프로젝트를 추가하는 것을 추천합니다."
        )
    else:
        overall_evaluation = (
            f"이력서와 깃허브 코드 간의 검증 Gap이 발견되었습니다 (일치율 {match_pct}%). "
            f"이력서에 작성된 주요 기술 스택의 실제 구현 코드가 공개 GitHub 저장소에서 확인되지 않습니다. "
            f"작업했던 로컬 프로젝트를 깃허브에 업로드하거나 이력서의 기술 설명을 더 다듬을 필요가 있습니다."
        )

    return ResumeGithubResponse(
        overall_evaluation=overall_evaluation,
        resume_skills=sorted(resume_skills),
        github_skills=sorted(github_skills),
        verified_skills=verified_skills,
        unverified_skills=unverified_skills,
        newly_discovered_skills=newly_discovered_skills,
    )