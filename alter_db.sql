-- ============================================================
-- next DB 스키마 변경 스크립트
-- 실행 방식: mysql -u root -p < alter_db.sql
-- 멱등성: ADD COLUMN IF NOT EXISTS (MySQL 8.0+)
--          ADD INDEX IF NOT EXISTS  (MySQL 8.0.29+)
-- 사용법: 변경이 필요한 블록만 주석 해제 후 실행
-- ============================================================

USE `next`;

-- ────────────────────────────────────────────
-- [컬럼 추가 예시]
-- ────────────────────────────────────────────

-- users 테이블에 컬럼 추가
-- ALTER TABLE users
--   ADD COLUMN IF NOT EXISTS profile_image VARCHAR(500) AFTER github_id,
--   ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE AFTER profile_image;

-- resumes 테이블에 컬럼 추가
-- ALTER TABLE resumes
--   ADD COLUMN IF NOT EXISTS file_url VARCHAR(500) AFTER content,
--   ADD COLUMN IF NOT EXISTS version SMALLINT UNSIGNED DEFAULT 1 AFTER file_url;

-- cover_letters 테이블에 컬럼 추가
-- ALTER TABLE cover_letters
--   ADD COLUMN IF NOT EXISTS target_company VARCHAR(255) AFTER title,
--   ADD COLUMN IF NOT EXISTS version SMALLINT UNSIGNED DEFAULT 1 AFTER target_company;

-- analysis_github 테이블에 컬럼 추가
-- ALTER TABLE analysis_github
--   ADD COLUMN IF NOT EXISTS error_message TEXT AFTER status;

-- analysis_gap 테이블에 컬럼 추가
-- ALTER TABLE analysis_gap
--   ADD COLUMN IF NOT EXISTS error_message TEXT AFTER status;

-- analysis_resume_github 테이블에 컬럼 추가
-- ALTER TABLE analysis_resume_github
--   ADD COLUMN IF NOT EXISTS error_message TEXT AFTER status;

-- integrated_analyses 테이블에 컬럼 추가
-- ALTER TABLE integrated_analyses
--   ADD COLUMN IF NOT EXISTS error_message TEXT AFTER status;

-- ────────────────────────────────────────────
-- [컬럼 타입 변경]
-- IF NOT EXISTS 미지원 → 실행 전 컬럼 존재 여부 확인 필요
-- ────────────────────────────────────────────

-- ALTER TABLE users
--   MODIFY COLUMN github_id VARCHAR(200);

-- ALTER TABLE job_urls
--   MODIFY COLUMN url VARCHAR(4096) NOT NULL;

-- ────────────────────────────────────────────
-- [인덱스 추가 - MySQL 8.0.29+]
-- ────────────────────────────────────────────

-- CREATE INDEX IF NOT EXISTS idx_resumes_user_active
--   ON resumes (user_id, is_active);

-- CREATE INDEX IF NOT EXISTS idx_cover_letters_user_active
--   ON cover_letters (user_id, is_active);

-- CREATE INDEX IF NOT EXISTS idx_analysis_github_user_status
--   ON analysis_github (user_id, status);

-- CREATE INDEX IF NOT EXISTS idx_analysis_gap_user_status
--   ON analysis_gap (user_id, status);

-- CREATE INDEX IF NOT EXISTS idx_analysis_rg_user_status
--   ON analysis_resume_github (user_id, status);

-- CREATE INDEX IF NOT EXISTS idx_integrated_user_status
--   ON integrated_analyses (user_id, status);

-- ────────────────────────────────────────────
-- [컬럼 삭제]
-- IF NOT EXISTS 미지원 → 실행 전 확인 필요
-- ────────────────────────────────────────────

-- ALTER TABLE users
--   DROP COLUMN IF EXISTS legacy_field;

-- ────────────────────────────────────────────
-- [테이블 추가 - 면접질문 저장 시 활성화]
-- ────────────────────────────────────────────

-- CREATE TABLE IF NOT EXISTS interview_questions (
--   question_id     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
--   user_id         BIGINT UNSIGNED NOT NULL,
--   cover_letter_id BIGINT UNSIGNED,
--   category        VARCHAR(50),
--   question_text   TEXT NOT NULL,
--   model_answer    TEXT,
--   difficulty      ENUM('easy','medium','hard'),
--   slot_order      TINYINT UNSIGNED,
--   created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
--   CONSTRAINT fk_iq_user
--     FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
--   CONSTRAINT fk_iq_cover_letter
--     FOREIGN KEY (cover_letter_id) REFERENCES cover_letters(cover_letter_id) ON DELETE SET NULL
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- [테이블 추가 - 챗봇 세션 (미래용)]
-- ────────────────────────────────────────────

-- CREATE TABLE IF NOT EXISTS chat_sessions (
--   session_id  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
--   user_id     BIGINT UNSIGNED NOT NULL,
--   context     ENUM('usage_guide','interview_prep','analysis_qa') DEFAULT 'usage_guide',
--   created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
--   CONSTRAINT fk_chat_sessions_user
--     FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- CREATE TABLE IF NOT EXISTS chat_messages (
--   message_id  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
--   session_id  BIGINT UNSIGNED NOT NULL,
--   role        ENUM('user','assistant') NOT NULL,
--   content     TEXT NOT NULL,
--   created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
--   CONSTRAINT fk_chat_messages_session
--     FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
