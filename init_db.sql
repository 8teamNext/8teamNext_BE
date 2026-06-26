-- ============================================================
-- next DB 초기화 스크립트
-- 실행 방식: mysql -u root -p < init_db.sql
-- 멱등성: CREATE IF NOT EXISTS → 이미 존재하면 스킵
-- ============================================================

CREATE DATABASE IF NOT EXISTS `next`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `next`;

-- ────────────────────────────────────────────
-- 회원
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  user_id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email                VARCHAR(255) UNIQUE,
  password_hash        VARCHAR(255),
  name                 VARCHAR(100),
  github_id            VARCHAR(100),
  default_resume       LONGTEXT,
  default_cover_letter LONGTEXT,
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 이력서
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resumes (
  resume_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED  ,
  title       VARCHAR(255),
  content     MEDIUMTEXT  ,
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_resumes_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 자기소개서
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cover_letters (
  cover_letter_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id         BIGINT UNSIGNED  ,
  title           VARCHAR(255),
  content         MEDIUMTEXT  ,
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_cover_letters_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 채용공고 URL 그룹 (A그룹, B그룹 ...)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_url_groups (
  group_id    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED  ,
  group_name  VARCHAR(100)  ,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_url_groups_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 채용공고 URL (그룹당 최대 5개, 앱 레벨에서 제한)
CREATE TABLE IF NOT EXISTS job_urls (
  url_id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  group_id    BIGINT UNSIGNED  ,
  url         VARCHAR(2048)  ,
  slot_order  TINYINT UNSIGNED  ,       -- 1~5 슬롯
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_group_slot (group_id, slot_order),
  CONSTRAINT fk_job_urls_group
    FOREIGN KEY (group_id) REFERENCES job_url_groups(group_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 비교분석 1: GitHub 포트폴리오 분석
-- models.py GithubAnalysisResponse 기반
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_github (
  analysis_github_id  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id             BIGINT UNSIGNED  ,
  repo_urls           JSON  ,           -- List[str] 입력 스냅샷
  job_urls            JSON  ,           -- List[str] 입력 스냅샷
  portfolio_rating    VARCHAR(50),
  overall_job_fit     TINYINT UNSIGNED,        -- 0~100
  strong_skills       JSON,                    -- List[str]
  weak_skills         JSON,                    -- List[str]
  readme_suggestions  JSON,                    -- List[str]
  repo_details        JSON,                    -- List[RepoDetail]
  job_comparisons     JSON,                    -- List[JobFitDetail]
  total_commits       INT UNSIGNED DEFAULT 0,
  active_weeks        SMALLINT UNSIGNED DEFAULT 0,
  status              ENUM('pending','done','error') DEFAULT 'pending',
  created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_analysis_github_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 비교분석 2: 스킬 갭 분석
-- models.py GapAnalysisResponse 기반
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_gap (
  analysis_gap_id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id              BIGINT UNSIGNED  ,
  repo_urls            JSON,                   -- List[str] optional
  job_urls             JSON  ,          -- List[str]
  proven_skills        JSON,                   -- List[str]
  missing_skills       JSON,                   -- List[str]
  discovered_skills    JSON,                   -- List[str]
  priority_skills      JSON,                   -- List[str]
  company_rankings     JSON,                   -- List[CompanyRanking]
  recommended_projects JSON,                   -- List[RecommendedProject]
  status               ENUM('pending','done','error') DEFAULT 'pending',
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_analysis_gap_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 비교분석 3: 이력서-GitHub 연계 분석
-- models.py ResumeGithubResponse 기반
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_resume_github (
  analysis_rg_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id                 BIGINT UNSIGNED  ,
  github_username         VARCHAR(100)  ,
  tech_stack              JSON  ,       -- List[str]
  overall_evaluation      TEXT,
  resume_skills           JSON,                -- List[str]
  github_skills           JSON,                -- List[str]
  verified_skills         JSON,                -- List[str]
  unverified_skills       JSON,                -- List[str]
  newly_discovered_skills JSON,                -- List[str]
  supplement_advice       TEXT,
  update_suggestion       TEXT,
  status                  ENUM('pending','done','error') DEFAULT 'pending',
  created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_analysis_rg_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- 통합분석
-- models.py UnifiedAnalysisResponse 기반
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS integrated_analyses (
  integrated_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id              BIGINT UNSIGNED  ,
  github_url           VARCHAR(2048),          -- 입력 스냅샷
  job_urls             JSON,                   -- List[str] 입력 스냅샷
  portfolio_rating     VARCHAR(50),
  overall_match_pct    TINYINT UNSIGNED,       -- 0~100
  skill_match_pct      TINYINT UNSIGNED,       -- 0~100
  active_weeks         SMALLINT UNSIGNED,
  total_commits        INT UNSIGNED,
  repo_coverage_pct    TINYINT UNSIGNED,       -- 0~100
  repo_count           SMALLINT UNSIGNED,
  github_analysis      JSON,                   -- UnifiedGithubPart
  resume_analysis      JSON,                   -- UnifiedResumePart
  skill_gap            JSON,                   -- UnifiedGapPart
  recommended_projects JSON,                   -- List[RecommendedProject]
  comparison_result    JSON,                   -- ComparisonResult
  status               ENUM('pending','done','error') DEFAULT 'pending',
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_integrated_analyses_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ────────────────────────────────────────────
-- Junction: 통합분석 ↔ 비교분석 3종
-- analysis_type으로 어느 테이블인지 구분 (polymorphic)
-- analysis_id는 각 타입 테이블의 PK 값 (앱 레벨 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS integrated_analysis_map (
  map_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  integrated_id BIGINT UNSIGNED  ,
  analysis_type ENUM('github','gap','resume_github')  ,
  analysis_id   BIGINT UNSIGNED  ,
  slot_order    TINYINT UNSIGNED,
  UNIQUE KEY uq_map_pair (integrated_id, analysis_type, analysis_id),
  CONSTRAINT fk_map_integrated
    FOREIGN KEY (integrated_id) REFERENCES integrated_analyses(integrated_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
