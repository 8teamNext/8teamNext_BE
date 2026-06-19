"""
GitHub 분석 서비스
- GitHub REST API로 실제 레포 데이터 수집
- 언어 비중 계산
- topics 수집
"""

import os
import asyncio
import httpx
from typing import Optional

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# 유저 존재 확인 
async def check_user_exists(client: httpx.AsyncClient, username: str) -> bool:
    try:
        res = await client.get(f"{BASE_URL}/users/{username}", headers=HEADERS)
        return res.status_code == 200
    except Exception:
        return False


# 레포 목록 수집 
async def fetch_repos(client: httpx.AsyncClient, username: str) -> list[dict]:
    """fork 제외, 최근 업데이트 순, 최대 20개"""
    try:
        res = await client.get(
            f"{BASE_URL}/users/{username}/repos",
            headers=HEADERS,
            params={
                "type": "owner",
                "sort": "updated",
                "per_page": 20,
            },
            timeout=10,
        )
        if res.status_code != 200:
            return []
        repos = res.json()
        return [r for r in repos if not r.get("fork", False)]
    except Exception:
        return []


# 레포별 언어 수집 
async def fetch_languages(client: httpx.AsyncClient, username: str, repo_name: str) -> dict:
    """빈 레포면 {} 반환"""
    try:
        res = await client.get(
            f"{BASE_URL}/repos/{username}/{repo_name}/languages",
            headers=HEADERS,
            timeout=10,
        )
        if res.status_code != 200:
            return {}
        return res.json()
    except Exception:
        return {}


# 레포별 topics 수집 
async def fetch_topics(client: httpx.AsyncClient, username: str, repo_name: str) -> list[str]:
    try:
        res = await client.get(
            f"{BASE_URL}/repos/{username}/{repo_name}/topics",
            headers={
                **HEADERS,
                "Accept": "application/vnd.github.mercy-preview+json",
            },
            timeout=10,
        )
        if res.status_code != 200:
            return []
        return res.json().get("names", [])
    except Exception:
        return []


# 언어 비중 계산
def calc_language_ratio(all_languages: dict[str, int]) -> dict[str, float]:
    """
    {"JavaScript": 14000, "TypeScript": 8000}
    → {"JavaScript": 63.6, "TypeScript": 36.4}
    """
    total = sum(all_languages.values())
    if total == 0:
        return {}
    return {
        lang: round(bytes_ / total * 100, 1)
        for lang, bytes_ in sorted(all_languages.items(), key=lambda x: x[1], reverse=True)
    }


# 메인 진입점
async def test_github(username: str) -> dict:
    """
    username을 받아 언어 비중 + topics 반환

    성공 반환:
    {
        "username": "octocat",
        "languages": {"JavaScript": 63.6, "TypeScript": 36.4},
        "topics": ["react", "nextjs"],
        "top_repos": ["repo1", "repo2"],
        "error": None
    }

    실패 반환:
    {
        "username": None or str,
        "error": "에러 메시지"
    }
    """
    username = username.strip()

    if not username:
        return {"username": None, "error": "GitHub 아이디를 입력해주세요."}

    async with httpx.AsyncClient() as client:
        # 1. 유저 존재 확인
        exists = await check_user_exists(client, username)
        if not exists:
            return {
                "username": username,
                "error": f"GitHub 유저 '{username}'를 찾을 수 없습니다.",
            }

        # 2. 레포 목록 수집
        repos = await fetch_repos(client, username)
        if not repos:
            return {
                "username": username,
                "error": "분석할 공개 레포지토리가 없습니다.",
            }

        # 3. 언어 + topics 병렬 수집
        language_tasks = [
            fetch_languages(client, username, repo["name"])
            for repo in repos
        ]
        topic_tasks = [
            fetch_topics(client, username, repo["name"])
            for repo in repos
        ]

        language_results = await asyncio.gather(*language_tasks)
        topic_results = await asyncio.gather(*topic_tasks)

        # 4. 언어 bytes 합산
        merged_languages: dict[str, int] = {}
        for lang_dict in language_results:
            for lang, bytes_ in lang_dict.items():
                merged_languages[lang] = merged_languages.get(lang, 0) + bytes_

        # 5. 비중 계산
        language_ratio = calc_language_ratio(merged_languages)

        # 6. topics 중복 제거 후 합산
        all_topics: list[str] = []
        for topics in topic_results:
            for topic in topics:
                if topic not in all_topics:
                    all_topics.append(topic)

        return {
            "username": username,
            "languages": language_ratio,
            "topics": all_topics,
            "top_repos": [repo["name"] for repo in repos],
            "error": None,
        }