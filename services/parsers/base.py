import re
from dataclasses import dataclass, field
from typing import Optional


# ── 기술스택 정규화 테이블 ─────────────────────────────────────────────────
TECH_ALIASES: dict[str, str] = {
#     "ai":"ai","ai":"pytorch","ai": "tensorflow", "ai":"keras", "ai":"scikit-learn", "ai":"pandas", "ai":"numpy","ai":"langchain", "ai":"openai", "ai":"huggingface", "ai":"mlflow", "ai":"kubeflow",
# "ai":"llm","ai":"rag",
    "react.js": "React", "reactjs": "React", "react": "React",
    "vue.js": "Vue", "vuejs": "Vue", "vue": "Vue",
    "next.js": "Next.js", "nextjs": "Next.js",
    "nuxt.js": "Nuxt.js", "nuxtjs": "Nuxt.js",
    "node.js": "Node.js", "nodejs": "Node.js",
    "typescript": "TypeScript", "ts": "TypeScript",
    "javascript": "JavaScript", "js": "JavaScript",
    "python": "Python",
    "java": "Java","Java":"자바","java":"java","java":"Java","자바":"Java","JAVA":"JAVA",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "spring boot": "Spring Boot", "springboot": "Spring Boot",
    "spring": "Spring",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis",
    "docker": "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "git": "Git",
    "graphql": "GraphQL",
    "rest api": "REST API", "restapi": "REST API",
    "flutter": "Flutter",
    "react native": "React Native",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "android": "Android",
    "ios": "iOS",
    "go": "Go", "golang": "Go",
    "rust": "Rust",
    "c++": "C++", "cpp": "C++",
    "c#": "C#",
    "ruby": "Ruby",
    "rails": "Ruby on Rails", "ruby on rails": "Ruby on Rails",
    "elasticsearch": "Elasticsearch", "elastic": "Elasticsearch",
    "kafka": "Kafka",
    "jenkins": "Jenkins",
    "terraform": "Terraform",
    
}

JOB_TYPE_KEYWORDS = {
    "신입": ["신입"],
    "경력": ["경력"],
    "무관": ["무관", "신입/경력", "경력/신입"],
}


def normalize_tech(raw: str) -> str:
    return TECH_ALIASES.get(raw.strip().lower(), raw.strip())


def extract_techs_from_text(text: str) -> list[str]:
    """텍스트에서 기술스택 키워드를 추출해 정규화된 목록으로 반환."""
    found = set()
    lower = text.lower()
    for alias in sorted(TECH_ALIASES.keys(), key=len, reverse=True):
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lower):
            found.add(TECH_ALIASES[alias])
    return sorted(found)


def detect_job_type(text: str) -> str:
    for job_type, keywords in JOB_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return job_type
    return ""


# ── 공통 데이터 클래스 ─────────────────────────────────────────────────────
@dataclass
class JobInfo:
    url: str
    title: str = ""
    company: str = ""
    job_type: str = ""
    tasks: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    raw_text: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "company": self.company,
            "job_type": self.job_type,
            "tasks": self.tasks,
            "tech_stack": self.tech_stack,
            "error": self.error,
        }