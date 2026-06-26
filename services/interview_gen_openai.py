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
- sample_answer_tip만 작성하고, 모범 답변 전문은 생성하지 않습니다.

[채용공고 분석 규칙]
채용공고가 제공된 경우, job_posting_analysis를 반드시 채워주세요.

- summary: 채용공고 내용만으로 작성, 자기소개서 내용 절대 포함 금지.
  형식: "회사명 · 직무명 — 공고 핵심을 한 문장으로"

- extracted_requirements: 공고에 명시된 기술·경험·자격 요건만 5~8개 추출.
  추측이나 일반적인 역량(예: "커뮤니케이션 능력") 제외, 구체적인 기술/경험 위주로. 경력/학력/도메인도 포함하도록.

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
      "sample_answer_tip": "답변 구조 설계 팁 (두 문장 이내)"
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


# ── 스타일·난이도 프롬프트 ────────────────────────────────────────────────────

_STYLE_PROMPTS = {
    "기본형": "",
    "압박형": """

[면접 스타일: 압박형 — 이 규칙은 질문 개인화 규칙보다 우선합니다]
당신은 지원자의 주장을 절대 그대로 받아들이지 않는 냉정한 시니어 면접관입니다.
모든 주장에는 증거를 요구하고, 모든 선택에는 근거를 추궁합니다.

[어조 규칙]
- 칭찬·공감·부드러운 도입부 없이 바로 본론으로 들어가세요.
- 질문 문장은 짧고 직접적으로 — "~하셨나요?" 대신 "~하셨다는 근거가 무엇인가요?"
- 지원자를 불편하게 만들되, 무례하지 않은 선을 유지하세요.

[질문 구성 규칙 — 7개 중 5개 이상을 아래 패턴으로 작성]

① 주장 검증 (2개 이상)
   자기소개서의 구체적 수치·성과·개선 주장에 직접 의문을 제기하세요.
   - "응답속도를 개선했다고 하셨는데, 개선 전후 수치를 어떻게 측정하셨나요?"
   - "그 결과가 본인 작업 덕분이라는 걸 어떻게 검증하셨나요?"

② 기여도 추궁 (1개 이상)
   팀 프로젝트에서 본인 기여가 과장됐을 가능성을 파고드세요.
   - "팀 프로젝트라고 하셨는데, 이 부분을 본인이 단독으로 구현하셨나요?"
   - "팀원이 없었다면 혼자 같은 결과를 낼 수 있었을까요?"

③ 대안 압박 (1개 이상)
   선택한 기술·방법 외에 다른 선택지가 있었음을 지적하세요.
   - "왜 하필 그 기술을 선택하셨나요? 대안을 검토하셨다면 무엇이었나요?"
   - "그 방법이 최선이었다는 걸 어떻게 확신하셨나요?"

④ 한계·실패 파고들기 (1개 이상)
   프로젝트의 부족한 점, 실패, 기술 부채를 직접 물어보세요.
   - "지금 그 코드를 다시 본다면 가장 부끄러운 부분이 어디인가요?"
   - "그 설계에서 가장 잘못된 판단은 무엇이었나요?"

[sample_answer_tip 작성 규칙]
각 질문의 tip에는 압박을 버티는 방법을 알려주세요.
- 수치나 근거가 없다면 솔직하게 인정하고 대신 무엇을 배웠는지로 전환하는 방법
- 대안 질문에는 선택 당시의 제약 조건(시간·팀 규모·기술 스택)을 근거로 제시하는 방법""",

    "균형형": """

[면접 스타일: 인성+기술 균형형 — 이 규칙은 질문 개인화 규칙보다 우선합니다]
당신은 기술 역량과 팀 문화 적합성을 동등하게 평가하는 면접관입니다.

질문 구성 규칙:
1. 기술 질문 5개: 자기소개서의 프로젝트·기술 경험 기반, 구체적 구현 방법 확인
2. 인성·협업 질문 2개: 아래 주제 중 선택하여 반드시 포함하세요.
   - 팀원과 기술적 의견이 충돌했던 경험과 해결 방식
   - 프로젝트 실패 또는 예상치 못한 문제를 극복한 경험
   - 팀에서 본인의 역할과 다른 팀원을 도운 구체적 사례
   - 성장하기 위해 스스로 시작한 학습이나 변화
3. 인성 질문은 "협업·소통" 카테고리로 분류하고, 자기소개서에 언급된 팀 프로젝트를 반드시 인용하세요.
4. 인성 질문의 sample_answer는 STAR 기법(상황-과제-행동-결과) 구조로 작성하세요.""",
}

_DIFFICULTY_PROMPTS = {
    "신입": """
[난이도: 신입]
신입 개발자를 대상으로 한 질문을 생성하세요.
- 기초 개념 이해, 학습 능력, 성장 가능성 위주로 질문하세요.
- 깊은 설계 경험보다는 배운 것을 어떻게 적용했는지를 묻는 방식으로 구성하세요.
- sample_answer는 실무 경험이 없어도 답할 수 있는 수준으로 작성하세요.""",
    "경력": """
[난이도: 경력 (3년 이상)]
경력 개발자를 대상으로 한 질문을 생성하세요.
- 아키텍처 설계, 트레이드오프 판단, 팀 기술 의사결정 경험을 묻는 질문을 포함하세요.
- 단순 구현 방법보다 "왜 그 선택을 했는가", "규모가 커지면 어떻게 대응할 것인가"를 중심으로 구성하세요.
- sample_answer는 실무 깊이가 드러나는 수준으로 작성하세요.""",
}


# ── 메인 함수 ──────────────────────────────────────────────────────────────────

def generate_interview_questions(
    cover_letter: str,
    job_posting: str = "",
    style: str = "기본형",
    difficulty: str = "신입",
) -> InterviewGenResponse:
    rule_error = _validate_cover_letter(cover_letter)
    if rule_error:
        raise ValueError(rule_error)

    client = _get_client()

    style_block = _STYLE_PROMPTS.get(style, "")
    difficulty_block = _DIFFICULTY_PROMPTS.get(difficulty, _DIFFICULTY_PROMPTS["신입"])
    system_prompt = SYSTEM_PROMPT + style_block + difficulty_block

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
            {"role": "system", "content": system_prompt},
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


def generate_followup_question(question: str, user_answer: str) -> dict:
    client = _get_client()

    system = """당신은 한국 IT 기업의 시니어 기술 면접관입니다.
지원자의 답변을 듣고 더 깊이 파고드는 꼬리질문을 1개 생성하세요.

규칙:
- 답변에서 구체적이지 않거나 증명이 필요한 부분을 타겟으로 하세요.
- 답변이 피상적이면 "그래서 실제로 어떻게 구현했나요?" 식으로 구체화를 요구하세요.
- 답변이 구체적이면 더 깊은 원리나 트레이드오프를 물으세요.
- 짧고 날카롭게 — 한 문장으로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{
  "followup_question": "꼬리질문 한 문장",
  "intent": "이 꼬리질문을 하는 이유 한 문장"
}"""

    user_content = f"[원래 질문]\n{question}\n\n[지원자 답변]\n{user_answer}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.5,
        max_tokens=512,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"followup_question": "답변을 좀 더 구체적으로 설명해주시겠어요?", "intent": ""}

    return {
        "followup_question": data.get("followup_question", ""),
        "intent": data.get("intent", ""),
    }


_SAMPLE_ANSWER_STYLE_BLOCKS = {
    "압박형": """
[스타일: 압박형]
- 수치·근거·대안을 반드시 포함하세요
- "왜 그 방법을 선택했는가"에 대한 논리적 근거를 명확히 하세요
- 약점이나 한계도 솔직하게 인정하고 극복 방법을 제시하세요""",
    "균형형": """
[스타일: 인성+기술 균형형]
- 기술적 내용과 함께 팀워크·협업 과정을 자연스럽게 포함하세요
- 인성 관련 질문은 STAR 기법(상황-과제-행동-결과) 구조로 작성하세요""",
}

_SAMPLE_ANSWER_DIFFICULTY_BLOCKS = {
    "신입": """
[난이도: 신입]
- 실무 경험이 없어도 답할 수 있는 수준으로 작성하세요
- 학습 과정과 성장 가능성을 드러내세요""",
    "경력": """
[난이도: 경력 3년+]
- 아키텍처 트레이드오프와 기술 의사결정 과정을 드러내세요
- 규모·성능·유지보수 관점에서 깊이 있는 답변을 작성하세요""",
}


def generate_sample_answer(
    question: str,
    cover_letter: str,
    intent: str,
    suggested_keywords: list,
    style: str = "기본형",
    difficulty: str = "신입",
) -> str:
    client = _get_client()

    style_block = _SAMPLE_ANSWER_STYLE_BLOCKS.get(style, "")
    difficulty_block = _SAMPLE_ANSWER_DIFFICULTY_BLOCKS.get(difficulty, _SAMPLE_ANSWER_DIFFICULTY_BLOCKS["신입"])

    system = f"""당신은 한국 IT 기업 기술 면접 코치입니다.
지원자의 자기소개서를 바탕으로 주어진 면접 질문에 대한 모범 답변을 작성하세요.

규칙:
- 자기소개서에 실제로 언급된 프로젝트·기술·경험만 활용하세요 (가상의 수치나 경험 추가 금지)
- 200~300자 분량으로 작성하세요
- 제시된 키워드를 자연스럽게 포함하세요{style_block}{difficulty_block}

반드시 아래 JSON 형식으로만 응답하세요:
{{"sample_answer": "모범 답변 내용"}}"""

    keywords_str = ", ".join(suggested_keywords)
    user_content = (
        f"[자기소개서]\n{cover_letter[:3000]}\n\n"
        f"[질문]\n{question}\n\n"
        f"[출제 의도]\n{intent}\n\n"
        f"[포함할 키워드]\n{keywords_str}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}

    return data.get("sample_answer", "")