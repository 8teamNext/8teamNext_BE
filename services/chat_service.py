"""챗봇 RAG 응답 생성 서비스."""
import os
from openai import AsyncOpenAI
from services.rag_service import retrieve

_SYSTEM_PROMPT = """당신은 'AI Career Copilot' 서비스의 친절한 안내 도우미입니다.
아래 [참고 문서]를 기반으로 사용자 질문에 정확하고 친절하게 한국어로 답변하세요.

[규칙]
- 반드시 [참고 문서] 내용을 기반으로 답변하세요.
- 서비스 기능과 무관한 질문은 "해당 내용은 서비스 도우미 범위 밖입니다"라고 안내하세요.
- 마크다운 형식을 사용하세요 (리스트, **강조** 활용).
- 단계별 안내는 번호 목록으로 작성하세요.
- 간결하게 답변하세요."""


async def chat_rag(session_history: list[dict], user_message: str) -> str:
    """
    RAG 기반 챗봇 응답 생성.
    session_history: [{"role": "user"|"assistant", "content": "..."}, ...]
    """
    context_docs = await retrieve(user_message, top_k=4)
    context_text = "\n\n---\n\n".join(context_docs) if context_docs else "관련 문서 없음"

    messages = [
        {
            "role": "system",
            "content": f"{_SYSTEM_PROMPT}\n\n[참고 문서]\n{context_text}",
        }
    ]
    # 최근 10개 메시지만 맥락으로 포함
    messages.extend(session_history[-10:])
    messages.append({"role": "user", "content": user_message})

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=600,
        temperature=0.3,
    )
    return resp.choices[0].message.content or "죄송합니다, 응답을 생성할 수 없습니다."
