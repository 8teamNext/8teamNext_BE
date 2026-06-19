import re
import urllib.parse
from typing import List, Set

# 동일 기술의 다른 표기를 하나의 정규명으로 통일
SKILL_ALIASES: dict[str, str] = {
    # HTML/CSS 계열
    "html":         "HTML/CSS",
    "css":          "HTML/CSS",
    "html/css":     "HTML/CSS",
    "scss":         "HTML/CSS",
    "sass":         "HTML/CSS",
    # React 계열
    "react":        "React",
    "react.js":     "React",
    "reactjs":      "React",
    # Node.js 계열
    "node":         "Node.js",
    "node.js":      "Node.js",
    "nodejs":       "Node.js",
    # Next.js 계열
    "next":         "Next.js",
    "next.js":      "Next.js",
    "nextjs":       "Next.js",
    # Vue.js 계열
    "vue":          "Vue.js",
    "vue.js":       "Vue.js",
    "vuejs":        "Vue.js",
    # Spring 계열 (Spring Boot 포함)
    "spring":       "Spring Boot",
    "spring boot":  "Spring Boot",
    "spring mvc":   "Spring Boot",
    # Git 계열
    "git":          "Git",
    "github":       "Git",
    "gitlab":       "Git",
    # Java
    "java":         "Java",
    "kotlin":       "Kotlin",
    # Python
    "python":       "Python",
    # DB 계열
    "mysql":        "MySQL",
    "mariadb":      "MySQL",
    "postgresql":   "PostgreSQL",
    "postgres":     "PostgreSQL",
    # CI/CD
    "ci/cd":        "CI/CD",
    "github actions": "CI/CD",
    "jenkins":      "CI/CD",
    "gitlab ci":    "CI/CD",
}


def normalize_skill(skill: str) -> str:
    """기술명을 정규화된 대표명으로 변환."""
    return SKILL_ALIASES.get(skill.lower(), skill)


def normalize_skill_set(skills: Set[str]) -> Set[str]:
    """기술 집합 전체를 정규화."""
    return {normalize_skill(s) for s in skills}

TECH_GLOSSARY = [
    # 백엔드 언어
    "Java", "Kotlin", "Python", "Go", "C", "C++", "C#", "PHP", "Ruby", "Rust", "Scala", "Groovy",

    # 프론트엔드 언어
    "JavaScript", "TypeScript", "HTML/CSS", "HTML", "CSS",

    # 모바일
    "Swift", "Dart", "Flutter", "Objective-C",

    # 백엔드 프레임워크
    "Spring Boot", "Spring", "Spring Data JPA", "Spring MVC", "Spring Security",
    "JPA", "Hibernate", "MyBatis",
    "Django", "FastAPI", "Flask",
    "Node.js", "Express", "NestJS",
    "Laravel", "Symfony", "CodeIgniter",
    "Ruby on Rails",
    "ASP.NET", ".NET",

    # 프론트엔드 프레임워크
    "React.js", "React", "Next.js", "Vue.js", "Nuxt.js", "Angular", "Svelte",
    "Redux", "Zustand", "Recoil", "Tailwind CSS", "SASS", "SCSS",

    # 데이터베이스
    "MySQL", "MariaDB", "PostgreSQL", "Oracle", "MSSQL", "SQLite",
    "MongoDB", "Redis", "Elasticsearch", "DynamoDB", "Cassandra", "CouchDB",
    "Cubrid", "Tibero", "Altibase",

    # 빌드 / 패키지
    "Gradle", "Maven", "npm", "Yarn", "Webpack", "Vite",

    # DevOps / 인프라
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Naver Cloud",
    "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI", "Travis CI",
    "CI/CD", "Terraform", "Ansible", "Nginx", "Apache",

    # 협업 / 버전관리
    "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence",

    # 메시징 / 캐싱
    "Kafka", "RabbitMQ", "ActiveMQ",

    # 기타
    "Linux", "GraphQL", "REST API", "gRPC", "WebSocket",
    "JUnit", "Mockito", "Jest", "Cypress",
    "Figma", "Swagger", "Postman",
]


def parse_skills_from_text(text: str) -> List[str]:
    if not text:
        return []
    found = []
    text_lower = text.lower()
    for tech in TECH_GLOSSARY:
        pattern = r'\b' + re.escape(tech.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found.append(tech)
    return found


def extract_name_from_url(url: str, default: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            domain_parts = parsed.netloc.split(".")
            return domain_parts[-2].title() if len(domain_parts) >= 2 else default
        parts = path.split("/")
        return parts[-1].replace("-", " ").replace("_", " ").title() or default
    except Exception:
        return default
