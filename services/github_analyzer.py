import asyncio
import base64
import json
import os
import re
import urllib.parse
import urllib.request
from typing import List, Optional, Set

from models import GithubAnalysisResponse, RepoDetail, JobFitDetail
from services.text_utils import parse_skills_from_text

GITHUB_API_BASE = "https://api.github.com"

LANGUAGE_TO_SKILL = {
    "Java": "Java", "Kotlin": "Kotlin",
    "JavaScript": "JavaScript", "TypeScript": "TypeScript",
    "Python": "Python", "Swift": "Swift", "Dart": "Dart",
    "Go": "Go", "C++": "C++", "Rust": "Rust", "Ruby": "Ruby",
    "HTML": "HTML/CSS", "CSS": "HTML/CSS", "SCSS": "HTML/CSS",
    "Shell": "Linux", "Dockerfile": "Docker",
}

JOB_REQUIRED_SKILLS = {
    "frontend": ["JavaScript", "TypeScript", "React.js", "HTML/CSS", "Next.js", "Vue.js"],
    "backend":  ["Java", "Spring Boot", "JPA", "MySQL", "Docker", "AWS", "Redis"],
    "android":  ["Kotlin", "Android SDK", "Jetpack Compose", "Coroutines", "Git"],
    "ios":      ["Swift", "iOS SDK", "SwiftUI", "Xcode"],
    "devops":   ["Docker", "Kubernetes", "AWS", "Linux", "CI/CD", "Git"],
    "python":   ["Python", "FastAPI", "Django", "PostgreSQL", "Docker"],
    "default":  ["Java", "Spring Boot", "JPA", "MySQL", "Docker", "AWS", "Git"],
}


def extract_username(url: str) -> str:
    """GitHub URL 또는 username 문자열에서 username 추출."""
    url = url.strip().rstrip("/")
    if "github.com/" in url:
        parts = urllib.parse.urlparse(url).path.strip("/").split("/")
        return parts[0] if parts else ""
    return url


async def _gh_get(path: str) -> Optional[object]:
    def _fetch():
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "spc-career-copilot",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        print(f"  [GitHub API] {'토큰O' if token else '토큰없음(rate limit위험)'} {path[:60]}")
        req = urllib.request.Request(GITHUB_API_BASE + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"  [_gh_get 오류] {path} → {type(e).__name__}: {e}")
            return None
    return await asyncio.to_thread(_fetch)


async def _get_commit_count(username: str, repo_name: str) -> int:
    """레포 전체 커밋 수를 Link 헤더로 추출."""
    def _fetch():
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "spc-career-copilot"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        path = f"/repos/{username}/{repo_name}/commits?per_page=1"
        req = urllib.request.Request(GITHUB_API_BASE + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                link = resp.getheader("Link", "")
                match = re.search(r'page=(\d+)>; rel="last"', link)
                if match:
                    return int(match.group(1))
                body = resp.read().decode()
                data = json.loads(body)
                return len(data) if isinstance(data, list) else 0
        except Exception as e:
            print(f"  [commit_count 오류] {repo_name}: {e}")
            return 0
    return await asyncio.to_thread(_fetch)


async def _get_active_weeks(username: str, repo_name: str) -> set:
    """최근 1년 커밋 날짜를 읽어 활동한 (연, 주차) 집합 반환."""
    from datetime import datetime, timezone, timedelta
    since = (datetime.now(timezone.utc) - timedelta(weeks=52)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _fetch():
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "spc-career-copilot"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        path = f"/repos/{username}/{repo_name}/commits?since={since}&per_page=100"
        req = urllib.request.Request(GITHUB_API_BASE + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return []

    data = await asyncio.to_thread(_fetch)
    weeks = set()
    latest_date = None
    if isinstance(data, list):
        for commit in data:
            try:
                date_str = commit["commit"]["author"]["date"]
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                weeks.add((dt.isocalendar()[0], dt.isocalendar()[1]))
                if latest_date is None or dt > latest_date:
                    latest_date = dt
            except Exception:
                pass
    print(f"  [active_weeks] {repo_name}: 조회기간={since[:10]} 이후, 커밋수={len(data) if isinstance(data, list) else '오류'}, 활동주={len(weeks)}, 최신커밋={latest_date.date() if latest_date else '없음'}")
    return weeks


async def _analyze_single_repo(username: str, repo: dict) -> Optional[dict]:
    """레포 하나를 비동기로 분석하여 상세 정보를 반환."""
    name = repo.get("name", "")
    if not name or repo.get("fork"):
        return None

    # 언어, README, 커밋 수, 활동 주차 병렬 요청
    langs_raw, readme_data, commit_count, active_week_set = await asyncio.gather(
        _gh_get(f"/repos/{username}/{name}/languages"),
        _gh_get(f"/repos/{username}/{name}/readme"),
        _get_commit_count(username, name),
        _get_active_weeks(username, name),
        return_exceptions=True,
    )

    # 언어 처리
    languages: List[str] = []
    skills: Set[str] = set()
    if isinstance(langs_raw, Exception):
        print(f"  [{name}] 언어 API 오류: {langs_raw}")
    elif isinstance(langs_raw, dict):
        languages = list(langs_raw.keys())[:6]
        for lang in languages:
            mapped = LANGUAGE_TO_SKILL.get(lang)
            if mapped:
                skills.add(mapped)

    # README 처리
    readme_text = ""
    if isinstance(readme_data, Exception):
        print(f"  [{name}] README API 오류: {readme_data}")
    elif isinstance(readme_data, dict) and readme_data.get("content"):
        try:
            readme_text = base64.b64decode(readme_data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            pass

    readme_skills = parse_skills_from_text(readme_text)
    desc_skills = parse_skills_from_text(repo.get("description") or "")
    topic_skills = parse_skills_from_text(" ".join(repo.get("topics") or []))
    skills.update(readme_skills)
    skills.update(desc_skills)
    skills.update(topic_skills)

    print(f"  [{name}] 언어:{languages} | 커밋:{commit_count if not isinstance(commit_count, Exception) else '오류'} | "
          f"README기술:{readme_skills} | desc기술:{desc_skills} | topic기술:{topic_skills}")

    # README 품질 평가
    readme_len = len(readme_text.strip())
    if readme_len > 800:
        readme_status = "우수"
    elif readme_len > 200:
        readme_status = "보통"
    else:
        readme_status = "미흡 (README 보완 필요)"

    stars = repo.get("stargazers_count", 0)
    quality_score = min(95, 55
        + min(stars * 3, 20)
        + (20 if readme_len > 800 else 10 if readme_len > 200 else 0)
        + (5 if isinstance(commit_count, int) and commit_count > 10 else 0))

    week_set = active_week_set if isinstance(active_week_set, set) else set()
    print(f"  [{name}] active_week_set 타입={type(active_week_set).__name__}, 활동주={len(week_set)}주 / 오류={active_week_set if isinstance(active_week_set, Exception) else ''}")

    return {
        "name": name,
        "url": repo.get("html_url", ""),
        "description": repo.get("description") or "",
        "primary_language": repo.get("language") or (languages[0] if languages else "Unknown"),
        "languages": languages,
        "stars": stars,
        "forks": repo.get("forks_count", 0),
        "commit_count": commit_count if isinstance(commit_count, int) else 0,
        "active_week_set": week_set,
        "readme_status": readme_status,
        "quality_score": quality_score,
        "skills": skills,
    }


def _detect_job_type(job_url: str) -> str:
    url = job_url.lower()
    if any(k in url for k in ["frontend", "react", "vue", "next"]):
        return "frontend"
    if any(k in url for k in ["android", "mobile"]):
        return "android"
    if any(k in url for k in ["ios", "swift"]):
        return "ios"
    if any(k in url for k in ["devops", "cloud", "infra", "k8s", "kubernetes"]):
        return "devops"
    if any(k in url for k in ["python", "data", "ml", "ai"]):
        return "python"
    if any(k in url for k in ["backend", "java", "spring", "node", "server"]):
        return "backend"
    return "default"


async def analyze_github(github_urls: List[str], job_urls: List[str]) -> GithubAnalysisResponse:
    username = extract_username(github_urls[0]) if github_urls else ""

    if not username:
        return GithubAnalysisResponse(
            portfolio_rating="분석 불가",
            overall_job_fit=0,
            strong_skills=[],
            weak_skills=[],
            readme_suggestions=["GitHub 계정명을 마이페이지에서 설정해주세요."],
            repo_details=[],
            job_comparisons=[],
        )

    # 사용자 정보 + 레포 목록 병렬 요청
    print(f"[GitHub] username={username} 요청 시작")
    user_info, repos_raw = await asyncio.gather(
        _gh_get(f"/users/{username}"),
        _gh_get(f"/users/{username}/repos?per_page=30&sort=updated&type=owner"),
    )
    print(f"[GitHub] user_info 타입={type(user_info).__name__}, repos_raw 타입={type(repos_raw).__name__}")
    if isinstance(repos_raw, list):
        print(f"[GitHub] 총 레포 수={len(repos_raw)}, 포크 제외={len([r for r in repos_raw if not r.get('fork')])}")
    else:
        print(f"[GitHub] repos_raw 내용: {str(repos_raw)[:200]}")

    if not isinstance(repos_raw, list):
        return GithubAnalysisResponse(
            portfolio_rating="분석 불가",
            overall_job_fit=0,
            strong_skills=[],
            weak_skills=[],
            readme_suggestions=["GitHub 사용자를 찾을 수 없습니다. 계정명을 확인해주세요."],
            repo_details=[],
            job_comparisons=[],
        )

    owned = [r for r in repos_raw if not r.get("fork")][:10]

    # 레포 병렬 분석
    raw_results = await asyncio.gather(
        *[_analyze_single_repo(username, repo) for repo in owned],
        return_exceptions=True,
    )

    all_skills: Set[str] = set()
    repo_details: List[RepoDetail] = []
    total_commits = 0
    merged_week_set: set = set()  # 전체 레포에 걸쳐 커밋 있는 (연, 주차) 합집합

    for res in raw_results:
        if not isinstance(res, dict):
            continue
        all_skills.update(res["skills"])
        total_commits += res["commit_count"]
        merged_week_set.update(res.get("active_week_set", set()))

        repo_details.append(RepoDetail(
            name=res["name"],
            url=res["url"],
            primary_language=res["primary_language"],
            languages=res["languages"],
            readme_status=res["readme_status"],
            stars=res["stars"],
            quality_score=res["quality_score"],
            description=res["description"] or f"{res['name']} 레포지토리",
            commit_count=res["commit_count"],
        ))

    # 최근 52주 중 실제 커밋 있는 주 수
    active_weeks = len(merged_week_set)

    strong_skills = sorted(all_skills)

    # 채용공고별 적합도 계산
    job_comparisons: List[JobFitDetail] = []
    all_required: Set[str] = set()

    for job_url in job_urls:
        job_type = _detect_job_type(job_url)
        required = JOB_REQUIRED_SKILLS.get(job_type, JOB_REQUIRED_SKILLS["default"])
        all_required.update(required)

        matched = [s for s in required if s in all_skills]
        missing = [s for s in required if s not in all_skills]
        fit = int(len(matched) / max(len(required), 1) * 100)

        try:
            domain = urllib.parse.urlparse(job_url).netloc.split(".")[-2].title()
        except Exception:
            domain = "Company"

        role_map = {
            "frontend": "프론트엔드 엔지니어",
            "backend": "백엔드 엔지니어",
            "android": "Android 개발자",
            "ios": "iOS 개발자",
            "devops": "DevOps 엔지니어",
            "python": "Python 개발자",
            "default": "백엔드 엔지니어",
        }
        job_comparisons.append(JobFitDetail(
            job_url=job_url,
            company_name=domain,
            role=role_map.get(job_type, "엔지니어"),
            match_percentage=fit,
            matched_skills=matched,
            missing_skills=missing,
        ))

    overall_fit = sum(j.match_percentage for j in job_comparisons) // max(len(job_comparisons), 1)
    weak_skills = sorted(s for s in all_required if s not in all_skills)[:6]

    avg_quality = sum(r.quality_score for r in repo_details) // max(len(repo_details), 1)
    portfolio_rating = (
        "매우 우수 (A+)" if avg_quality >= 85
        else "우수 (B+)" if avg_quality >= 70
        else "보통 (C)"
    )

    readme_suggestions: List[str] = []
    poor_readme = [r.name for r in repo_details if r.readme_status.startswith("미흡")]
    if poor_readme:
        readme_suggestions.append(f"README 보완 필요 레포: {', '.join(poor_readme[:3])}. 프로젝트 소개, 기술 스택, 실행 방법을 작성하세요.")
    if active_weeks < 15:
        readme_suggestions.append(f"최근 1년 중 {active_weeks}주만 커밋 활동이 있었습니다. 꾸준한 커밋 습관(주 3회 이상)으로 성실도를 높이세요.")
    if total_commits < 30:
        readme_suggestions.append("전체 커밋 수가 적습니다. 작은 단위로 자주 커밋하는 습관을 들이세요.")
    if len(repo_details) < 3:
        readme_suggestions.append("공개 레포지토리 수를 늘려 포트폴리오 다양성을 확보하세요.")
    if not readme_suggestions:
        readme_suggestions.append("전반적으로 레포지토리 관리 상태가 좋습니다. 아키텍처 다이어그램을 추가하면 더욱 전문적으로 보입니다.")

    return GithubAnalysisResponse(
        portfolio_rating=portfolio_rating,
        overall_job_fit=overall_fit,
        strong_skills=strong_skills,
        weak_skills=weak_skills,
        readme_suggestions=readme_suggestions,
        repo_details=repo_details,
        job_comparisons=job_comparisons,
        total_commits=total_commits,
        active_weeks=active_weeks,
    )
