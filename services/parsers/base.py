import re
from dataclasses import dataclass, field
from typing import Optional


# ── 기술스택 정규화 테이블 ─────────────────────────────────────────────────
TECH_ALIASES: dict[str, str] = {
    # ai
    "ai": "AI",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "pandas": "pandas",
    "numpy": "numpy",
    "langchain": "LangChain",
    "openai": "OpenAI",
    "huggingface": "Hugging Face",
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "llm": "LLM",
    "rag": "RAG",

    # 프론트엔드
    "react.js": "React", "reactjs": "React", "react": "React",
    "vue.js": "Vue", "vuejs": "Vue", "vue": "Vue",
    "next.js": "Next.js", "nextjs": "Next.js",
    "nuxt.js": "Nuxt.js", "nuxtjs": "Nuxt.js",
    "node.js": "Node.js", "nodejs": "Node.js",
    "typescript": "TypeScript", "ts": "TypeScript",
    "javascript": "JavaScript", "js": "JavaScript",

    # 백엔드
    "python": "Python",
    "java": "Java", "자바": "Java",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "spring boot": "Spring Boot", "springboot": "Spring Boot",
    "spring": "Spring",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",

    # DB
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",

    # 인프라
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "git": "Git",

    # 기타
    "graphql": "GraphQL",
    "rest api": "REST API",
    "restapi": "REST API",
    "flutter": "Flutter",
    "react native": "React Native",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "android": "Android",
    "ios": "iOS",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "ruby": "Ruby",
    "rails": "Ruby on Rails",
    "ruby on rails": "Ruby on Rails",
    "elasticsearch": "Elasticsearch",
    "elastic": "Elasticsearch",
    "kafka": "Kafka",
    "jenkins": "Jenkins",
    "terraform": "Terraform",
}


JOB_TYPE_KEYWORDS = {
    "신입": ["신입"],
    "경력": ["경력"],
    "신입/경력": ["신입/경력"],
    "무관": ["무관", "신입/경력", "경력/신입"],
}


def normalize_tech(raw: str) -> str:
    return TECH_ALIASES.get(raw.strip().lower(), raw.strip())


def extract_techs_from_text(text: str) -> list[str]:
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
    skills: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    raw_text: str = ""
    error: Optional[str] = None

# ────────────────────────────────────────────────────────────────
# Position
# ────────────────────────────────────────────────────────────────

@dataclass
class PositionInfo:
    position_name: Optional[str] = None

    tasks: list[str] = field(default_factory=list)

    requirements: list[str] = field(default_factory=list)

    preferred: list[str] = field(default_factory=list)

    tech_stack: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "position_name": self.position_name,
            "tasks": self.tasks,
            "requirements": self.requirements,
            "preferred": self.preferred,
            "tech_stack": self.tech_stack,
        }


# ────────────────────────────────────────────────────────────────
# JobInfo
# ────────────────────────────────────────────────────────────────

@dataclass
class JobInfo:
    url: str

    title: str = ""

    company: str = ""

    job_type: str = ""

    positions: list[PositionInfo] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)

    # 전체 공고 기준 기술스택 (매칭용)
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
            "positions": [p.to_dict() for p in self.positions],
            "tech_stack": self.tech_stack,
            "error": self.error,
        }