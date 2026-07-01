"""챗봇 API Blueprint: 세션 관리 + RAG 메시지 처리."""
import asyncio
import json
import queue as _queue
import threading
from flask import Blueprint, request, jsonify, Response
from db import fetch_all, fetch_one, execute
from services.chat_service import chat_rag, chat_rag_stream

chatbot_bp = Blueprint("chatbot", __name__)


# ── 세션 목록 조회 ────────────────────────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions", methods=["GET"])
async def list_sessions():
    owner = request.args.get("owner", "").strip()
    if not owner:
        return jsonify({"detail": "owner 파라미터가 필요합니다."}), 400
    rows = await fetch_all(
        """SELECT session_id, owner_key, title, created_at, updated_at
           FROM chat_sessions
           WHERE owner_key = %s
           ORDER BY updated_at DESC""",
        (owner,),
    )
    # datetime 직렬화
    for r in rows:
        for k in ("created_at", "updated_at"):
            if r.get(k):
                r[k] = r[k].isoformat()
    return jsonify(rows)


# ── 세션 생성 ─────────────────────────────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions", methods=["POST"])
async def create_session():
    data = request.get_json() or {}
    owner = data.get("owner", "").strip()
    title = data.get("title", "새 대화").strip() or "새 대화"
    if not owner:
        return jsonify({"detail": "owner가 필요합니다."}), 400

    session_id = await execute(
        "INSERT INTO chat_sessions (owner_key, title) VALUES (%s, %s)",
        (owner, title),
    )
    row = await fetch_one(
        "SELECT session_id, owner_key, title, created_at, updated_at FROM chat_sessions WHERE session_id = %s",
        (session_id,),
    )
    if row:
        for k in ("created_at", "updated_at"):
            if row.get(k):
                row[k] = row[k].isoformat()
    return jsonify(row), 201


# ── 세션 삭제 ─────────────────────────────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions/<int:session_id>", methods=["DELETE"])
async def delete_session(session_id: int):
    await execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
    return jsonify({"status": "success"})


# ── 세션 제목 수정 ────────────────────────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions/<int:session_id>", methods=["PATCH"])
async def rename_session(session_id: int):
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"detail": "title이 필요합니다."}), 400
    await execute(
        "UPDATE chat_sessions SET title = %s WHERE session_id = %s",
        (title, session_id),
    )
    return jsonify({"status": "success"})


# ── 메시지 목록 조회 ──────────────────────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions/<int:session_id>/messages", methods=["GET"])
async def get_messages(session_id: int):
    rows = await fetch_all(
        """SELECT message_id, session_id, role, content, created_at
           FROM chat_messages
           WHERE session_id = %s
           ORDER BY created_at ASC""",
        (session_id,),
    )
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(rows)


# ── 메시지 전송 (RAG) ─────────────────────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions/<int:session_id>/messages", methods=["POST"])
async def send_message(session_id: int):
    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"detail": "content가 필요합니다."}), 400

    # 세션 유효성 확인
    session = await fetch_one(
        "SELECT session_id FROM chat_sessions WHERE session_id = %s",
        (session_id,),
    )
    if not session:
        return jsonify({"detail": "세션을 찾을 수 없습니다."}), 404

    # 이전 메시지 히스토리 조회
    history = await fetch_all(
        "SELECT role, content FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
        (session_id,),
    )
    session_history = [{"role": r["role"], "content": r["content"]} for r in history]

    # 사용자 메시지 저장
    await execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'user', %s)",
        (session_id, content),
    )

    # RAG 기반 응답 생성
    try:
        reply = await chat_rag(session_history, content)
    except Exception as e:
        reply = f"죄송합니다, 응답 생성 중 오류가 발생했습니다: {str(e)}"

    # 어시스턴트 응답 저장
    await execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'assistant', %s)",
        (session_id, reply),
    )

    # 첫 메시지이면 세션 제목을 자동으로 설정, 아니면 updated_at만 갱신
    if not history:
        auto_title = content[:30] + ("..." if len(content) > 30 else "")
        await execute(
            "UPDATE chat_sessions SET title = %s, updated_at = NOW() WHERE session_id = %s",
            (auto_title, session_id),
        )
    else:
        await execute(
            "UPDATE chat_sessions SET updated_at = NOW() WHERE session_id = %s",
            (session_id,),
        )

    return jsonify({"role": "assistant", "content": reply})


# ── 메시지 전송 (RAG, SSE 스트리밍) ──────────────────────────────────────
@chatbot_bp.route("/api/chat/sessions/<int:session_id>/messages/stream", methods=["POST"])
async def send_message_stream(session_id: int):
    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"detail": "content가 필요합니다."}), 400

    session = await fetch_one(
        "SELECT session_id FROM chat_sessions WHERE session_id = %s",
        (session_id,),
    )
    if not session:
        return jsonify({"detail": "세션을 찾을 수 없습니다."}), 404

    history = await fetch_all(
        "SELECT role, content FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
        (session_id,),
    )
    session_history = [{"role": r["role"], "content": r["content"]} for r in history]
    is_first = not history

    await execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'user', %s)",
        (session_id, content),
    )

    # Flask는 WSGI라 async generator를 직접 반환할 수 없으므로
    # 별도 스레드에서 새 이벤트 루프로 LLM 스트리밍을 실행하고
    # Queue로 동기 generator에 청크를 전달한다.
    q: _queue.Queue = _queue.Queue()

    async def _producer():
        full_reply = ""
        try:
            async for chunk in chat_rag_stream(session_history, content):
                full_reply += chunk
                q.put(json.dumps({"chunk": chunk}, ensure_ascii=False))
        except Exception:
            full_reply = "죄송합니다, 응답 생성 중 오류가 발생했습니다."
            q.put(json.dumps({"chunk": full_reply, "error": True}, ensure_ascii=False))

        await execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'assistant', %s)",
            (session_id, full_reply),
        )
        if is_first:
            auto_title = content[:30] + ("..." if len(content) > 30 else "")
            await execute(
                "UPDATE chat_sessions SET title = %s, updated_at = NOW() WHERE session_id = %s",
                (auto_title, session_id),
            )
        else:
            await execute(
                "UPDATE chat_sessions SET updated_at = NOW() WHERE session_id = %s",
                (session_id,),
            )
        q.put(json.dumps({"done": True}, ensure_ascii=False))
        q.put(None)  # sentinel

    def _run_producer():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_producer())
        except Exception:
            q.put(json.dumps({"chunk": "죄송합니다, 오류가 발생했습니다.", "error": True}, ensure_ascii=False))
            q.put(json.dumps({"done": True}, ensure_ascii=False))
            q.put(None)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    threading.Thread(target=_run_producer, daemon=True).start()

    def _sync_generate():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return Response(
        _sync_generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── RAG 문서 재인덱싱 (관리자용) ─────────────────────────────────────────
@chatbot_bp.route("/api/chat/reindex", methods=["POST"])
async def reindex_docs():
    from services.rag_service import index_documents
    result = await index_documents()
    return jsonify(result)
