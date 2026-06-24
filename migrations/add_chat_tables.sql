-- 챗봇 세션 및 메시지 테이블
-- 실행: mysql -u root -p next < migrations/add_chat_tables.sql

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id  INT          NOT NULL AUTO_INCREMENT,
    owner_key   VARCHAR(255) NOT NULL COMMENT 'github_username (사용자 식별자)',
    title       VARCHAR(255) NOT NULL DEFAULT '새 대화',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id),
    INDEX idx_owner_updated (owner_key, updated_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id  INT                      NOT NULL AUTO_INCREMENT,
    session_id  INT                      NOT NULL,
    role        ENUM('user','assistant') NOT NULL,
    content     TEXT                     NOT NULL,
    created_at  DATETIME                 NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (message_id),
    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id) ON DELETE CASCADE,
    INDEX idx_session_created (session_id, created_at ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
