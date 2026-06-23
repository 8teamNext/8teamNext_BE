import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from models import InterviewGenResponse, InterviewQuestion, JobPostingAnalysis

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY가 .env에 설정되어 있지 않습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


# ── Rule-based 검증 ──────────────────────────────────────────────────────────

_CODE_PATTERNS = [
    r'git\s+config\s+--global',
    r'pip\s+install\s+\S+',
    r'npm\s+install\s+\S+',
    r'sk-proj-[A-Za-z0-9_-]{20,}',
    r'AIzaSy[A-Za-z0-9_-]{30,}',
    r'def\s+\w+\s*\(.*\)\s*:',
    r'public\s+(class|static|void)\s+\w+',
    r'^\s*#{1,6}\s+.+',
    r'-{4,}',
]

_KOREAN_PATTERN = re.compile(r'[가-힣]')


def _validate_cover_letter(text: str) -> str | None:
    stripped = text.strip()

    if len(stripped) < 50:
        return "자기소개서가 너무 짧습니다. 최소 50자 이상 입력해주세요."

    if len(stripped) > 15000:
        return "자기소개서가 너무 깁니다. 15,000자 이하로 입력해주세요."

    for pattern in _CODE_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE | re.MULTILINE):
            return "자기소개서가 아닌 코드 또는 메모로 보입니다. 실제 자기소개서를 입력해주세요."

    korean_chars = len(_KOREAN_PATTERN.findall(stripped))
    if korean_chars < 10:
        return "자기소개서에 한국어 내용이 너무 적습니다. 한국어로 작성된 자기소개서를 입력해주세요."

    return None


# ── System Prompt ─────────────────────────────────────────────────────────────

CATEGORIES = ["기술 구현", "트러블슈팅", "시스템 설계", "협업·소통", "CS 기초", "DevOps"]

SYSTEM_PROMPT = f"""당신은 한국 IT 기업의 시니어 기술 면접관입니다.
지원자의 자기소개서와 채용공고를 분석하여 맞춤형 기술 면접 질문을 생성합니다.

[검증 규칙]
입력된 텍스트가 아래 중 하나에 해당하면 질문을 생성하지 말고 error 필드만 채워서 반환하세요.
- 자기소개서가 아닌 단순 메모, 공부 노트, 코드 스니펫인 경우
- 의미 있는 경험·기술·프로젝트 내용이 전혀 없는 경우
- 무작위 텍스트나 테스트 입력인 경우

[카테고리 규칙]
각 질문에 아래 목록 중 가장 적합한 카테고리를 정확히 하나 선택하세요.

- 기술 구현: 특정 기술·라이브러리·패턴의 구현 방법 (JWT, JPA, DTO, ORM, 디자인 패턴, REST API 설계 등)
- 트러블슈팅: 실제 겪은 버그·성능 이슈·장애 해결 경험 (N+1, 메모리 누수, 동시성 문제 등)
- 시스템 설계: 전체 아키텍처·데이터 모델·인프라 구조 설계 (MSA, 캐싱 전략, DB 스키마 설계 등)
- 협업·소통: 팀워크·코드 리뷰·의사결정 과정·갈등 해결 경험
- CS 기초: 운영체제·네트워크·자료구조·알고리즘 등 컴퓨터 과학 이론 지식
- DevOps: Docker·CI/CD·AWS·배포 파이프라인·모니터링 등 인프라 운영

[질문 개인화 규칙 — 가장 중요]
질문 생성 전, 자기소개서에서 아래 항목을 먼저 식별하세요.
① 참여한 프로젝트명 또는 팀/회사명
② 사용한 기술·라이브러리·프레임워크
③ 직접 해결한 문제 또는 개선 사례
④ 본인이 담당한 역할과 기여

질문 중 3개 이상은 반드시 위 항목 중 하나를 명시적으로 인용해서 만드세요.
- 질문 문장 안에 자기소개서의 구체적인 프로젝트명·기술명·경험을 그대로 넣으세요.
  예) "자기소개서에서 [프로젝트명]에서 Redis 캐시 적용으로 응답 속도를 개선했다고 하셨는데..."
- 자기소개서에 없는 가상의 경험을 추가하거나 일반적인 질문을 만들지 마세요.
- 7개 질문이 서로 다른 경험·기술을 다루도록 분산하세요.
- 서로 다른 기술을 억지로 연관시키지 마세요.
- sample_answer는 자기소개서의 실제 경험을 토대로 작성하세요 (가상의 수치나 경험 추가 금지).

[채용공고 분석 규칙]
채용공고가 제공된 경우, job_posting_analysis를 반드시 채워주세요.

- summary: 채용공고 내용만으로 작성, 자기소개서 내용 절대 포함 금지.
  형식: "회사명 · 직무명 — 공고 핵심을 한 문장으로"

- extracted_requirements: 공고에 명시된 기술·경험·자격 요건만 5~8개 추출.
  추측이나 일반적인 역량(예: "커뮤니케이션 능력") 제외, 구체적인 기술/경험 위주로.

- matched: 자기소개서에 해당 역량의 직접적인 증거(프로젝트명, 기술 사용 사례)가 있는 항목만.
  증거 없이 "있을 것 같다"는 추정으로 포함하지 마세요.

- unmatched: 공고 요구사항 중 자기소개서에 전혀 언급되지 않은 항목만.

채용공고가 없으면 job_posting_analysis는 null로 반환하세요.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.

정상 응답:
{{
  "error": null,
  "questions": [
    {{
      "category": "카테고리 (위 목록 중 하나)",
      "question": "심도 있는 기술 면접 질문",
      "intent": "출제 의도 (왜 이 질문을 하는지 한 문장)",
      "suggested_keywords": ["핵심키워드1", "핵심키워드2", "핵심키워드3"],
      "sample_answer_tip": "답변 구조 설계 팁 (두 문장 이내)",
      "sample_answer": "200~400자 분량의 구체적인 모범 답변 예시"
    }}
  ],
  "job_posting_analysis": {{
    "summary": "회사명 · 직무명 — 공고 핵심을 한 문장으로",
    "extracted_requirements": ["요구사항1", "요구사항2"],
    "matched": ["일치하는 역량1", "일치하는 역량2"],
    "unmatched": ["부족한 역량1", "부족한 역량2"]
  }}
}}

검증 실패 응답:
{{
  "error": "자기소개서가 아닌 것으로 판단된 구체적인 이유",
  "questions": [],
  "job_posting_analysis": null
}}"""


# ── 메인 함수 ──────────────────────────────────────────────────────────────────

def generate_interview_questions(cover_letter: str, job_posting: str = "") -> InterviewGenResponse:
    rule_error = _validate_cover_letter(cover_letter)
    if rule_error:
        raise ValueError(rule_error)

    client = _get_client()

    user_parts = [f"[자기소개서]\n{cover_letter}"]
    if job_posting and job_posting.strip():
        user_parts.append(f"[채용공고]\n{job_posting.strip()}")

    user_parts.append(
        "위 내용을 분석하여 실전 기술 면접 질문 7개를 생성해주세요. "
        "자기소개서에 언급된 기술·프로젝트·트러블슈팅 경험을 기반으로 하고, "
        "채용공고가 있다면 채용공고의 요구 역량과 연계하여 질문을 구성하세요."
    )
    user_content = "\n\n".join(user_parts)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(json_match.group()) if json_match else {}

    if data.get("error"):
        raise ValueError(data["error"])

    questions = [
        InterviewQuestion(
            id=i + 1,
            category=q.get("category", "기술 구현") if q.get("category") in CATEGORIES else "기술 구현",
            question=q.get("question", ""),
            intent=q.get("intent", ""),
            suggested_keywords=q.get("suggested_keywords", []),
            sample_answer_tip=q.get("sample_answer_tip", ""),
            sample_answer=q.get("sample_answer", ""),
        )
        for i, q in enumerate(data.get("questions", []))
        if q.get("question")
    ]

    job_posting_analysis = None
    analysis_data = data.get("job_posting_analysis")
    if analysis_data and isinstance(analysis_data, dict):
        job_posting_analysis = JobPostingAnalysis(
            summary=analysis_data.get("summary", ""),
            extracted_requirements=analysis_data.get("extracted_requirements", []),
            matched=analysis_data.get("matched", []),
            unmatched=analysis_data.get("unmatched", []),
        )

    return InterviewGenResponse(questions=questions, job_posting_analysis=job_posting_analysis)