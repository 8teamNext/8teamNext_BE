import os
import json
import aiomysql
from typing import Optional, Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────
# 커넥션 풀 싱글톤
# ────────────────────────────────────────────
_pool: Optional[aiomysql.Pool] = None


async def get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            db=os.getenv("DB_NAME", "next"),
            charset="utf8mb4",
            autocommit=False,
            minsize=2,
            maxsize=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


# ────────────────────────────────────────────
# 단일 쿼리 실행 헬퍼
# ────────────────────────────────────────────
async def fetch_all(sql: str, args: tuple = ()) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchall()


async def fetch_one(sql: str, args: tuple = ()) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchone()


async def execute(sql: str, args: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE. INSERT는 lastrowid 반환."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, args)
            await conn.commit()
            return cur.lastrowid


# ────────────────────────────────────────────
# 트랜잭션 컨텍스트 매니저
# 여러 쿼리를 묶을 때 사용: async with transaction() as cur:
# ────────────────────────────────────────────
@asynccontextmanager
async def transaction():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await conn.begin()
                yield cur
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise


# ────────────────────────────────────────────
# JSON 직렬화 헬퍼 (Pydantic 모델 → DB 저장용)
# ────────────────────────────────────────────
def to_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o))


# ────────────────────────────────────────────
# 비교분석 1: GitHub 포트폴리오 분석 저장
# 패턴: pending insert → LLM 호출 → done update
# ────────────────────────────────────────────
async def insert_analysis_github_pending(user_id: int, repo_urls: list, job_urls: list) -> int:
    return await execute(
        """INSERT INTO analysis_github
           (user_id, repo_urls, job_urls, status)
           VALUES (%s, %s, %s, 'pending')""",
        (user_id, to_json(repo_urls), to_json(job_urls)),
    )


async def update_analysis_github_done(analysis_github_id: int, response) -> None:
    await execute(
        """UPDATE analysis_github SET
           portfolio_rating    = %s,
           overall_job_fit     = %s,
           strong_skills       = %s,
           weak_skills         = %s,
           readme_suggestions  = %s,
           repo_details        = %s,
           job_comparisons     = %s,
           total_commits       = %s,
           active_weeks        = %s,
           status              = 'done'
           WHERE analysis_github_id = %s""",
        (
            response.portfolio_rating,
            response.overall_job_fit,
            to_json(response.strong_skills),
            to_json(response.weak_skills),
            to_json(response.readme_suggestions),
            to_json([r.model_dump() for r in response.repo_details]),
            to_json([j.model_dump() for j in response.job_comparisons]),
            response.total_commits,
            response.active_weeks,
            analysis_github_id,
        ),
    )


async def update_analysis_github_error(analysis_github_id: int) -> None:
    await execute(
        "UPDATE analysis_github SET status = 'error' WHERE analysis_github_id = %s",
        (analysis_github_id,),
    )


# ────────────────────────────────────────────
# 비교분석 2: 스킬 갭 분석 저장
# ────────────────────────────────────────────
async def insert_analysis_gap_pending(user_id: int, repo_urls: list, job_urls: list) -> int:
    return await execute(
        """INSERT INTO analysis_gap
           (user_id, repo_urls, job_urls, status)
           VALUES (%s, %s, %s, 'pending')""",
        (user_id, to_json(repo_urls), to_json(job_urls)),
    )


async def update_analysis_gap_done(analysis_gap_id: int, response) -> None:
    await execute(
        """UPDATE analysis_gap SET
           proven_skills        = %s,
           missing_skills       = %s,
           discovered_skills    = %s,
           priority_skills      = %s,
           company_rankings     = %s,
           recommended_projects = %s,
           status               = 'done'
           WHERE analysis_gap_id = %s""",
        (
            to_json(response.proven_skills),
            to_json(response.missing_skills),
            to_json(response.discovered_skills),
            to_json(response.priority_skills),
            to_json([c.model_dump() for c in response.company_rankings]),
            to_json([p.model_dump() for p in response.recommended_projects]),
            analysis_gap_id,
        ),
    )


async def update_analysis_gap_error(analysis_gap_id: int) -> None:
    await execute(
        "UPDATE analysis_gap SET status = 'error' WHERE analysis_gap_id = %s",
        (analysis_gap_id,),
    )


# ────────────────────────────────────────────
# 비교분석 3: 이력서-GitHub 연계 분석 저장
# ────────────────────────────────────────────
async def insert_analysis_rg_pending(user_id: int, github_username: str, tech_stack: list) -> int:
    return await execute(
        """INSERT INTO analysis_resume_github
           (user_id, github_username, tech_stack, status)
           VALUES (%s, %s, %s, 'pending')""",
        (user_id, github_username, to_json(tech_stack)),
    )


async def update_analysis_rg_done(analysis_rg_id: int, response) -> None:
    await execute(
        """UPDATE analysis_resume_github SET
           overall_evaluation      = %s,
           resume_skills           = %s,
           github_skills           = %s,
           verified_skills         = %s,
           unverified_skills       = %s,
           newly_discovered_skills = %s,
           supplement_advice       = %s,
           update_suggestion       = %s,
           status                  = 'done'
           WHERE analysis_rg_id = %s""",
        (
            response.overall_evaluation,
            to_json(response.resume_skills),
            to_json(response.github_skills),
            to_json(response.verified_skills),
            to_json(response.unverified_skills),
            to_json(response.newly_discovered_skills),
            response.supplement_advice,
            response.update_suggestion,
            analysis_rg_id,
        ),
    )


async def update_analysis_rg_error(analysis_rg_id: int) -> None:
    await execute(
        "UPDATE analysis_resume_github SET status = 'error' WHERE analysis_rg_id = %s",
        (analysis_rg_id,),
    )


# ────────────────────────────────────────────
# 통합분석 저장 + Junction 연결 (트랜잭션)
# ────────────────────────────────────────────
async def insert_integrated_pending(user_id: int, github_url: str, job_urls: list) -> int:
    return await execute(
        """INSERT INTO integrated_analyses
           (user_id, github_url, job_urls, status)
           VALUES (%s, %s, %s, 'pending')""",
        (user_id, github_url, to_json(job_urls)),
    )


async def update_integrated_done(integrated_id: int, response) -> None:
    await execute(
        """UPDATE integrated_analyses SET
           portfolio_rating     = %s,
           overall_match_pct    = %s,
           skill_match_pct      = %s,
           active_weeks         = %s,
           total_commits        = %s,
           repo_coverage_pct    = %s,
           repo_count           = %s,
           github_analysis      = %s,
           resume_analysis      = %s,
           skill_gap            = %s,
           recommended_projects = %s,
           comparison_result    = %s,
           status               = 'done'
           WHERE integrated_id = %s""",
        (
            response.portfolio_rating,
            response.overall_match_pct,
            response.skill_match_pct,
            response.active_weeks,
            response.total_commits,
            response.repo_coverage_pct,
            response.repo_count,
            to_json(response.github_analysis.model_dump()),
            to_json(response.resume_analysis.model_dump()),
            to_json(response.skill_gap.model_dump()),
            to_json([p.model_dump() for p in response.recommended_projects]),
            to_json(response.comparison_result.model_dump()),
            integrated_id,
        ),
    )


async def update_integrated_error(integrated_id: int) -> None:
    await execute(
        "UPDATE integrated_analyses SET status = 'error' WHERE integrated_id = %s",
        (integrated_id,),
    )


async def link_integrated_analyses(
    integrated_id: int,
    analysis_refs: list[dict],  # [{"type": "github"|"gap"|"resume_github", "id": int}, ...]
) -> None:
    """통합분석과 비교분석들을 Junction 테이블로 연결 (트랜잭션)."""
    async with transaction() as cur:
        for order, ref in enumerate(analysis_refs, start=1):
            await cur.execute(
                """INSERT IGNORE INTO integrated_analysis_map
                   (integrated_id, analysis_type, analysis_id, slot_order)
                   VALUES (%s, %s, %s, %s)""",
                (integrated_id, ref["type"], ref["id"], order),
            )


# ────────────────────────────────────────────
# 분석 이력 조회 (3개 테이블 UNION)
# ────────────────────────────────────────────
async def get_analysis_history(user_id: int, limit: int = 20) -> list[dict]:
    sql = """
        SELECT 'github'         AS analysis_type,
               analysis_github_id AS analysis_id,
               portfolio_rating   AS summary,
               status,
               created_at
        FROM analysis_github WHERE user_id = %s

        UNION ALL

        SELECT 'gap'            AS analysis_type,
               analysis_gap_id  AS analysis_id,
               JSON_UNQUOTE(JSON_EXTRACT(priority_skills, '$[0]')) AS summary,
               status,
               created_at
        FROM analysis_gap WHERE user_id = %s

        UNION ALL

        SELECT 'resume_github'  AS analysis_type,
               analysis_rg_id   AS analysis_id,
               LEFT(overall_evaluation, 50) AS summary,
               status,
               created_at
        FROM analysis_resume_github WHERE user_id = %s

        ORDER BY created_at DESC
        LIMIT %s
    """
    return await fetch_all(sql, (user_id, user_id, user_id, limit))
