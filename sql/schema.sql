CREATE DATABASE IF NOT EXISTS loan_chatbot
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE loan_chatbot;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS user_states;
DROP TABLE IF EXISTS credit_scores;
DROP TABLE IF EXISTS amendment_requests;
DROP TABLE IF EXISTS repayment_records;
DROP TABLE IF EXISTS repayment_schedules;
DROP TABLE IF EXISTS contract_attachments;
DROP TABLE IF EXISTS contract_versions;
DROP TABLE IF EXISTS loan_contracts;
DROP TABLE IF EXISTS loan_project_members;
DROP TABLE IF EXISTS loan_projects;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    line_user_id VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(100),
    phone VARCHAR(30),
    email VARCHAR(255),
    status ENUM('active', 'blocked', 'deleted') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS loan_projects (
    project_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    invite_code VARCHAR(20) NOT NULL UNIQUE,
    created_by BIGINT UNSIGNED NOT NULL,
    creator_role ENUM('borrower', 'lender') NOT NULL,
    principal_amount DECIMAL(12, 2) NULL,
    annual_interest_rate DECIMAL(6, 3) NULL,
    term_months INT UNSIGNED NULL,
    repayment_method ENUM('equal_payment', 'equal_principal', 'interest_only', 'bullet') NULL,
    repayment_day TINYINT UNSIGNED NULL,
    status ENUM(
        'waiting_join',
        'paired',
        'pending_terms',
        'pending_borrower_confirm',
        'active',
        'overdue',
        'amendment_pending',
        'completed',
        'cancelled'
    ) NOT NULL DEFAULT 'waiting_join',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_loan_projects_created_by
        FOREIGN KEY (created_by) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_loan_projects_amount CHECK (principal_amount IS NULL OR principal_amount > 0),
    CONSTRAINT chk_loan_projects_rate CHECK (annual_interest_rate IS NULL OR annual_interest_rate >= 0),
    CONSTRAINT chk_loan_projects_term CHECK (term_months IS NULL OR term_months > 0),
    CONSTRAINT chk_loan_projects_repayment_day CHECK (repayment_day IS NULL OR repayment_day BETWEEN 1 AND 31),
    INDEX idx_loan_projects_invite_code (invite_code),
    INDEX idx_loan_projects_created_by_status (created_by, status),
    INDEX idx_loan_projects_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS loan_project_members (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    role ENUM('borrower', 'lender') NOT NULL,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_loan_project_members_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_loan_project_members_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE KEY uk_project_member_user (project_id, user_id),
    UNIQUE KEY uk_project_member_role (project_id, role),
    INDEX idx_loan_project_members_user_role (user_id, role),
    INDEX idx_loan_project_members_project_role (project_id, role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS loan_contracts (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL UNIQUE,
    current_version_id BIGINT UNSIGNED NULL,
    contract_number VARCHAR(50) NOT NULL UNIQUE,
    status ENUM('pending_borrower_confirm', 'active', 'completed', 'cancelled', 'defaulted') NOT NULL DEFAULT 'pending_borrower_confirm',
    accepted_by_borrower_at DATETIME NULL,
    activated_at DATETIME NULL,
    completed_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_loan_contracts_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_loan_contracts_project_status (project_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contract_versions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL,
    loan_contract_id BIGINT UNSIGNED NOT NULL,
    version_no INT UNSIGNED NOT NULL,
    source_type ENUM('initial', 'amendment') NOT NULL DEFAULT 'initial',
    amendment_request_id BIGINT UNSIGNED NULL,
    principal_amount DECIMAL(12, 2) NOT NULL,
    annual_interest_rate DECIMAL(6, 3) NOT NULL DEFAULT 0.000,
    term_months INT UNSIGNED NOT NULL,
    repayment_method ENUM('equal_payment', 'equal_principal', 'interest_only', 'bullet') NOT NULL,
    repayment_day TINYINT UNSIGNED NOT NULL,
    effective_date DATE NOT NULL,
    contract_text MEDIUMTEXT,
    created_by_user_id BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contract_versions_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_contract_versions_contract
        FOREIGN KEY (loan_contract_id) REFERENCES loan_contracts(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_contract_versions_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_contract_versions_amount CHECK (principal_amount > 0),
    CONSTRAINT chk_contract_versions_rate CHECK (annual_interest_rate >= 0),
    CONSTRAINT chk_contract_versions_term CHECK (term_months > 0),
    CONSTRAINT chk_contract_versions_repayment_day CHECK (repayment_day BETWEEN 1 AND 31),
    UNIQUE KEY uk_contract_versions_contract_version (loan_contract_id, version_no),
    INDEX idx_contract_versions_project (project_id),
    INDEX idx_contract_versions_effective_date (effective_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE loan_contracts
    ADD CONSTRAINT fk_loan_contracts_current_version
    FOREIGN KEY (current_version_id) REFERENCES contract_versions(id)
    ON DELETE SET NULL ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS contract_attachments (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL,
    loan_contract_id BIGINT UNSIGNED NULL,
    contract_version_id BIGINT UNSIGNED NULL,
    uploaded_by_user_id BIGINT UNSIGNED NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_mime_type VARCHAR(100),
    file_size_bytes BIGINT UNSIGNED,
    attachment_type ENUM('identity', 'proof', 'contract_pdf', 'receipt', 'other') NOT NULL DEFAULT 'other',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contract_attachments_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_contract_attachments_contract
        FOREIGN KEY (loan_contract_id) REFERENCES loan_contracts(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_contract_attachments_version
        FOREIGN KEY (contract_version_id) REFERENCES contract_versions(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_contract_attachments_uploader
        FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_contract_attachments_mime
        CHECK (file_mime_type IS NULL OR file_mime_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')),
    CONSTRAINT chk_contract_attachments_size
        CHECK (file_size_bytes IS NULL OR file_size_bytes <= 10485760),
    INDEX idx_contract_attachments_project (project_id),
    INDEX idx_contract_attachments_contract (loan_contract_id),
    INDEX idx_contract_attachments_version (contract_version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS repayment_schedules (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL,
    loan_contract_id BIGINT UNSIGNED NOT NULL,
    contract_version_id BIGINT UNSIGNED NOT NULL,
    period_no INT UNSIGNED NOT NULL,
    due_date DATE NOT NULL,
    principal_due DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    interest_due DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    total_due DECIMAL(12, 2) NOT NULL,
    adjusted_from_schedule_id BIGINT UNSIGNED NULL,
    status ENUM('pending', 'paid', 'overdue', 'adjusted') NOT NULL DEFAULT 'pending',
    paid_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_repayment_schedules_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_schedules_contract
        FOREIGN KEY (loan_contract_id) REFERENCES loan_contracts(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_schedules_version
        FOREIGN KEY (contract_version_id) REFERENCES contract_versions(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_schedules_adjusted_from
        FOREIGN KEY (adjusted_from_schedule_id) REFERENCES repayment_schedules(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_repayment_schedules_amount CHECK (total_due >= 0),
    UNIQUE KEY uk_repayment_schedules_contract_period (loan_contract_id, period_no),
    INDEX idx_repayment_schedules_project_status (project_id, status),
    INDEX idx_repayment_schedules_due_status (due_date, status),
    INDEX idx_repayment_schedules_contract_status (loan_contract_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS repayment_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL,
    repayment_schedule_id BIGINT UNSIGNED NOT NULL,
    loan_contract_id BIGINT UNSIGNED NOT NULL,
    payer_user_id BIGINT UNSIGNED NOT NULL,
    receiver_user_id BIGINT UNSIGNED NOT NULL,
    paid_amount DECIMAL(12, 2) NOT NULL,
    paid_at DATETIME NOT NULL,
    payment_method ENUM('cash', 'bank_transfer', 'line_pay', 'other') NOT NULL DEFAULT 'bank_transfer',
    proof_attachment_id BIGINT UNSIGNED NULL,
    status ENUM('pending_confirmation', 'confirmed', 'rejected') NOT NULL DEFAULT 'pending_confirmation',
    confirmed_at DATETIME NULL,
    confirmed_by_user_id BIGINT UNSIGNED NULL,
    note VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_repayment_records_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_records_schedule
        FOREIGN KEY (repayment_schedule_id) REFERENCES repayment_schedules(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_records_contract
        FOREIGN KEY (loan_contract_id) REFERENCES loan_contracts(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_records_payer
        FOREIGN KEY (payer_user_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_records_receiver
        FOREIGN KEY (receiver_user_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_records_proof
        FOREIGN KEY (proof_attachment_id) REFERENCES contract_attachments(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_repayment_records_confirmer
        FOREIGN KEY (confirmed_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_repayment_records_paid_amount CHECK (paid_amount > 0),
    INDEX idx_repayment_records_project (project_id),
    INDEX idx_repayment_records_schedule (repayment_schedule_id),
    INDEX idx_repayment_records_contract (loan_contract_id),
    INDEX idx_repayment_records_payer_paid_at (payer_user_id, paid_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS amendment_requests (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT UNSIGNED NOT NULL,
    loan_contract_id BIGINT UNSIGNED NOT NULL,
    requested_by_user_id BIGINT UNSIGNED NOT NULL,
    reviewed_by_user_id BIGINT UNSIGNED NULL,
    reason TEXT NOT NULL,
    proposed_principal_amount DECIMAL(12, 2) NULL,
    proposed_annual_interest_rate DECIMAL(6, 3) NULL,
    proposed_term_months INT UNSIGNED NULL,
    proposed_repayment_method ENUM('equal_payment', 'equal_principal', 'interest_only', 'bullet') NULL,
    proposed_repayment_day TINYINT UNSIGNED NULL,
    proposed_effective_date DATE NULL,
    status ENUM('pending_borrower_confirm', 'accepted', 'rejected', 'cancelled', 'applied') NOT NULL DEFAULT 'pending_borrower_confirm',
    accepted_at DATETIME NULL,
    rejected_at DATETIME NULL,
    applied_contract_version_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_amendment_requests_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_amendment_requests_contract
        FOREIGN KEY (loan_contract_id) REFERENCES loan_contracts(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_amendment_requests_requester
        FOREIGN KEY (requested_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_amendment_requests_reviewer
        FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_amendment_requests_applied_version
        FOREIGN KEY (applied_contract_version_id) REFERENCES contract_versions(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_amendment_requests_amount CHECK (proposed_principal_amount IS NULL OR proposed_principal_amount > 0),
    CONSTRAINT chk_amendment_requests_rate CHECK (proposed_annual_interest_rate IS NULL OR proposed_annual_interest_rate >= 0),
    CONSTRAINT chk_amendment_requests_term CHECK (proposed_term_months IS NULL OR proposed_term_months > 0),
    CONSTRAINT chk_amendment_requests_repayment_day CHECK (proposed_repayment_day IS NULL OR proposed_repayment_day BETWEEN 1 AND 31),
    INDEX idx_amendment_requests_project_status (project_id, status),
    INDEX idx_amendment_requests_contract_status (loan_contract_id, status),
    INDEX idx_amendment_requests_requester (requested_by_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE contract_versions
    ADD CONSTRAINT fk_contract_versions_amendment_request
    FOREIGN KEY (amendment_request_id) REFERENCES amendment_requests(id)
    ON DELETE SET NULL ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS credit_scores (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    project_id BIGINT UNSIGNED NULL,
    loan_contract_id BIGINT UNSIGNED NULL,
    repayment_record_id BIGINT UNSIGNED NULL,
    repayment_schedule_id BIGINT UNSIGNED NULL,
    event_type ENUM(
        'initial',
        'on_time_payment',
        'late_payment',
        'partial_payment',
        'overdue',
        'contract_completed',
        'manual_adjustment'
    ) NOT NULL,
    score_delta INT NOT NULL DEFAULT 0,
    score_after INT NOT NULL,
    note VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_credit_scores_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_credit_scores_project
        FOREIGN KEY (project_id) REFERENCES loan_projects(project_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_credit_scores_contract
        FOREIGN KEY (loan_contract_id) REFERENCES loan_contracts(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_credit_scores_repayment_record
        FOREIGN KEY (repayment_record_id) REFERENCES repayment_records(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_credit_scores_repayment_schedule
        FOREIGN KEY (repayment_schedule_id) REFERENCES repayment_schedules(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_credit_scores_score_after CHECK (score_after BETWEEN 300 AND 850),
    INDEX idx_credit_scores_user_created (user_id, created_at),
    INDEX idx_credit_scores_project (project_id),
    INDEX idx_credit_scores_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_states (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL UNIQUE,
    state_key VARCHAR(80) NOT NULL,
    state_data JSON NULL,
    expires_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_states_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_user_states_state_key (state_key),
    INDEX idx_user_states_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
