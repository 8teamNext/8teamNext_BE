import asyncio
import base64
import io
import os
import json
import re
import urllib.request
from typing import List, Set, Optional
from models import ResumeGithubResponse
from services.text_utils import parse_skills_from_text
from services.llm_analyzer import generate_resume_github_advice, generate_overall_evaluation


# ── 이력서 검증 ──────────────────────────────────────────────────────────────

# 이력서 구조 키워드
RESUME_STRUCTURE_KEYWORDS = [
    "경력", "학력", "이력서", "자기소개", "포트폴리오", "인턴", "신입",
    "재직", "졸업", "전공", "자격증", "수상", "연락처", "생년월일",
    "프로젝트 경험", "주요 경험", "기술 스택", "보유 기술",
]

# 기술 키워드 — 대한민국 30대 IT기업 채용공고 기준
TECH_KEYWORDS = [
    # ── 언어 ──────────────────────────────────────────────
    "java", "kotlin", "python", "javascript", "typescript", "go", "golang",
    "scala", "swift", "dart", "c++", "c#", "php", "ruby", "rust",

    # ── 백엔드 프레임워크 ──────────────────────────────────
    "spring", "spring boot", "spring framework", "spring batch", "spring security",
    "spring webflux", "ktor", "quarkus", "micronaut",
    "django", "fastapi", "flask",
    "node", "node.js", "express", "nestjs", "koa",
    "rails", "laravel",

    # ── 프론트엔드 / 앱 ────────────────────────────────────
    "react", "vue", "vue.js", "angular", "next.js", "nuxt", "nuxt.js",
    "svelte", "flutter", "react native",
    "html", "css", "sass", "webpack", "vite",

    # ── 데이터베이스 ──────────────────────────────────────
    "mysql", "postgresql", "postgres", "oracle", "mariadb", "mssql",
    "mongodb", "dynamodb", "cassandra", "hbase", "couchbase",
    "redis", "memcached",
    "elasticsearch", "opensearch", "solr",
    "clickhouse", "hive", "presto", "trino",
    "bigquery", "snowflake",

    # ── ORM / 데이터 접근 ─────────────────────────────────
    "jpa", "hibernate", "mybatis", "querydsl", "sqlalchemy", "prisma",

    # ── 클라우드 ──────────────────────────────────────────
    "aws", "gcp", "azure", "ncp", "naver cloud",
    "ec2", "s3", "lambda", "rds", "eks", "ecs",

    # ── 인프라 / DevOps ────────────────────────────────────
    "docker", "kubernetes", "k8s", "helm", "istio", "argocd",
    "terraform", "ansible", "puppet", "chef",
    "jenkins", "github actions", "gitlab ci", "circleci", "teamcity",
    "nginx", "apache", "tomcat", "netty",
    "linux", "bash", "shell",

    # ── 메시지 큐 / 스트리밍 ──────────────────────────────
    "kafka", "rabbitmq", "activemq", "sqs", "sns", "pubsub",
    "flink", "spark", "storm", "airflow",

    # ── API / 통신 ────────────────────────────────────────
    "restful", "rest api", "graphql", "grpc", "websocket",
    "openapi", "swagger",

    # ── 모니터링 / 관측 ───────────────────────────────────
    "prometheus", "grafana", "elk", "kibana", "logstash",
    "datadog", "sentry", "jaeger", "zipkin", "newrelic",

    # ── 테스트 ────────────────────────────────────────────
    "junit", "mockito", "jest", "cypress", "selenium", "playwright",
    "testcontainers",

    # ── 버전관리 / 협업 ───────────────────────────────────
    "git", "github", "gitlab", "bitbucket", "jira", "confluence",

    # ── 보안 / 인증 ───────────────────────────────────────
    "oauth", "jwt", "spring security", "keycloak", "iam",

    # ── AI / ML ───────────────────────────────────────────
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy",
    "langchain", "openai", "huggingface", "mlflow", "kubeflow",
    "llm", "rag",

    # ── 기타 ──────────────────────────────────────────────
    "ci/cd", "msa", "microservice", "ddd", "tdd", "agile", "scrum",
    "rxjava", "coroutine", "webflux",
]

# 공부 노트/메모로 판단하는 패턴 — 이력서에는 절대 없는 것들
_NOTE_PATTERNS = [
    r'-{4,}',                          # ---- 구분선
    r'git\s+config\s+--global',        # git 설정 명령어
    r'pip\s+install\s+\S+',            # pip install
    r'sk-proj-[A-Za-z0-9_-]{20,}',    # OpenAI API 키
    r'AIzaSy[A-Za-z0-9_-]{30,}',      # Google API 키
]

# 이력서 필수 개인정보 패턴 — 실제 이력서라면 반드시 하나 이상 존재
_CONTACT_PATTERNS = [
    r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}',               # 이메일
    r'\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}',           # 전화번호
    r'github\.com/[\w-]+\s',                          # GitHub 프로필 URL
    r'linkedin\.com/in/',                             # LinkedIn
]

# 실제 경력 기간 패턴 — 이력서에만 등장하는 날짜 범위
_EXPERIENCE_DATE_PATTERNS = [
    r'20\d{2}[.\-/]\d{1,2}\s*[~\-–]\s*(?:20\d{2}|현재|present)',  # 2020.03 ~ 2023.06
    r'20\d{2}년\s*\d{1,2}월\s*[~\-–]',                             # 2020년 3월 ~
]


async def validate_resume_text(text: str) -> dict:
    """이력서 내용 여부를 검증합니다."""
    if not text or len(text.strip()) < 50:
        return {"valid": False, "reason": "텍스트가 너무 짧습니다. 이력서 내용을 입력해주세요."}

    # 1. 공부 노트/메모 패턴이 있으면 즉시 거부
    for pattern in _NOTE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "valid": False,
                "reason": "이력서 형식의 내용이 아닙니다. 개인 메모나 학습 노트가 아닌 실제 이력서를 입력해주세요."
            }

    text_lower = text.lower()

    # 2. 개인 연락처 또는 경력 날짜 패턴 확인 (실제 이력서 필수 요소)
    has_contact = any(re.search(p, text, re.IGNORECASE) for p in _CONTACT_PATTERNS)
    has_experience_date = any(re.search(p, text) for p in _EXPERIENCE_DATE_PATTERNS)

    if not has_contact and not has_experience_date:
        return {
            "valid": False,
            "reason": "이력서 형식의 내용이 아닙니다. 이메일, 전화번호, 경력 기간(예: 2022.03 ~ 2024.06) 등 이력서 필수 정보를 포함해주세요."
        }

    # 3. 이력서 구조 키워드 확인
    if not any(kw in text_lower for kw in RESUME_STRUCTURE_KEYWORDS):
        return {
            "valid": False,
            "reason": "이력서 형식의 내용이 아닙니다. 경력, 학력, 프로젝트, 기술 스택 등 이력서 내용을 입력해주세요."
        }

    # 4. 기술 키워드 확인
    if not any(kw in text_lower for kw in TECH_KEYWORDS):
        return {
            "valid": False,
            "reason": "기술 스택 정보가 감지되지 않았습니다. 보유 기술을 이력서에 포함해주세요."
        }

    return {"valid": True, "reason": ""}


# ── PDF 추출 ──────────────────────────────────────────────────────────────────

async def extract_pdf_text(file_bytes: bytes) -> str:
    """PDF 바이너리에서 텍스트를 추출합니다."""
    def _parse():
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    return await asyncio.to_thread(_parse)


# ── GitHub 분석 ───────────────────────────────────────────────────────────────

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


async def _gh_get(path: str, extra_headers: dict = None) -> Optional[object]:
    def _fetch():
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "spc-resume-analyzer",
            **(extra_headers or {}),
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(GITHUB_API_BASE + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None
    return await asyncio.to_thread(_fetch)


def _decode_readme(content: str, encoding: str) -> str:
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return ""


async def _fetch_repo_skills(username: str, repo: dict) -> Set[str]:
    """레포 하나에서 기술 스택을 추출 — 병렬 실행 단위."""
    name = repo.get("name", "")
    if not name or repo.get("fork"):
        return set()

    skills: Set[str] = set()

    langs = await _gh_get(f"/repos/{username}/{name}/languages")
    if isinstance(langs, dict):
        for lang in langs:
            skill = LANGUAGE_TO_SKILL.get(lang)
            if skill:
                skills.add(skill)

    readme_data = await _gh_get(f"/repos/{username}/{name}/readme")
    if isinstance(readme_data, dict):
        readme_text = _decode_readme(
            readme_data.get("content", ""),
            readme_data.get("encoding", ""),
        )
        skills.update(parse_skills_from_text(readme_text))

    desc = repo.get("description") or ""
    skills.update(parse_skills_from_text(desc))

    topics: List[str] = repo.get("topics") or []
    skills.update(parse_skills_from_text(" ".join(topics)))

    return skills


async def _extract_github_skills(username: str) -> Set[str]:
    """GitHub 사용자의 레포지토리들을 병렬로 분석해 기술 스택을 추출."""
    repos = await _gh_get(f"/users/{username}/repos?per_page=30&sort=updated&type=owner")
    if not isinstance(repos, list) or not repos:
        return set()

    target_repos = [r for r in repos[:8] if r.get("name") and not r.get("fork")]

    results = await asyncio.gather(
        *[_fetch_repo_skills(username, repo) for repo in target_repos],
        return_exceptions=True,
    )

    skills: Set[str] = set()
    for result in results:
        if isinstance(result, set):
            skills.update(result)
    return skills


async def analyze_resume_github(
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
    github_skills = await _extract_github_skills(github_username)

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
    match_pct = round(ratio * 100)

    # 4. LLM 병렬 생성
    overall_evaluation, advice = await asyncio.gather(
        generate_overall_evaluation(
            verified_skills=verified_skills,
            unverified_skills=unverified_skills,
            newly_discovered_skills=newly_discovered_skills,
            match_pct=match_pct,
            github_username=github_username,
        ),
        generate_resume_github_advice(
            verified_skills=verified_skills,
            unverified_skills=unverified_skills,
            newly_discovered_skills=newly_discovered_skills,
            match_pct=match_pct,
        ),
    )

    return ResumeGithubResponse(
        overall_evaluation=overall_evaluation,
        resume_skills=sorted(resume_skills),
        github_skills=sorted(github_skills),
        verified_skills=verified_skills,
        unverified_skills=unverified_skills,
        newly_discovered_skills=newly_discovered_skills,
        supplement_advice=advice["supplement_advice"],
        update_suggestion=advice["update_suggestion"],
    )
