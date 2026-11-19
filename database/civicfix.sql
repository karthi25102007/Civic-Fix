-- CivicFix database schema and demo data
-- MySQL 8.0+  |  Charset: utf8mb4
-- The seeding statements use INSERT IGNORE so repeated imports never duplicate demo rows.

CREATE DATABASE IF NOT EXISTS civicfix
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE civicfix;

CREATE TABLE IF NOT EXISTS departments (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    code VARCHAR(30) NOT NULL UNIQUE,
    description TEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaint_categories (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    slug VARCHAR(120) NOT NULL UNIQUE,
    icon VARCHAR(60) NULL,
    description VARCHAR(255) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(191) NOT NULL UNIQUE,
    phone VARCHAR(30) NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('citizen', 'admin', 'staff') NOT NULL DEFAULT 'citizen',
    department_id INT UNSIGNED NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_role (role),
    INDEX idx_users_department (department_id),
    CONSTRAINT fk_users_department FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaints (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tracking_number VARCHAR(32) NOT NULL UNIQUE,
    citizen_id INT UNSIGNED NOT NULL,
    category_id INT UNSIGNED NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    additional_details TEXT NULL,
    location_address VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 7) NULL,
    longitude DECIMAL(10, 7) NULL,
    status ENUM('Submitted', 'Under Review', 'Verified', 'Assigned',
                'In Progress', 'Resolved', 'Reopened', 'Rejected')
        NOT NULL DEFAULT 'Submitted',
    priority ENUM('Low', 'Medium', 'High', 'Urgent') NOT NULL DEFAULT 'Medium',
    suggested_priority ENUM('Low', 'Medium', 'High', 'Urgent') NULL,
    priority_reason VARCHAR(500) NULL,
    is_public TINYINT(1) NOT NULL DEFAULT 1,
    rejection_reason TEXT NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_complaints_citizen (citizen_id),
    INDEX idx_complaints_category (category_id),
    INDEX idx_complaints_status (status),
    INDEX idx_complaints_priority (priority),
    INDEX idx_complaints_created (created_at),
    INDEX idx_complaints_location (latitude, longitude),
    CONSTRAINT fk_complaints_citizen FOREIGN KEY (citizen_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_complaints_category FOREIGN KEY (category_id)
        REFERENCES complaint_categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaint_assignments (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT UNSIGNED NOT NULL,
    department_id INT UNSIGNED NOT NULL,
    staff_id INT UNSIGNED NULL,
    assigned_by INT UNSIGNED NULL,
    note VARCHAR(500) NULL,
    is_current TINYINT(1) NOT NULL DEFAULT 1,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_assignments_complaint (complaint_id),
    INDEX idx_assignments_staff (staff_id),
    INDEX idx_assignments_department (department_id),
    CONSTRAINT fk_assignments_complaint FOREIGN KEY (complaint_id)
        REFERENCES complaints(id) ON DELETE CASCADE,
    CONSTRAINT fk_assignments_department FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_assignments_staff FOREIGN KEY (staff_id)
        REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_assignments_assigned_by FOREIGN KEY (assigned_by)
        REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaint_updates (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NULL,
    update_type ENUM('status', 'note', 'priority', 'assignment',
                     'progress', 'resolution', 'escalation', 'reopen', 'support') NOT NULL DEFAULT 'status',
    from_status VARCHAR(40) NULL,
    to_status VARCHAR(40) NULL,
    body TEXT NULL,
    is_public TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_updates_complaint (complaint_id, created_at),
    INDEX idx_updates_user (user_id),
    CONSTRAINT fk_updates_complaint FOREIGN KEY (complaint_id)
        REFERENCES complaints(id) ON DELETE CASCADE,
    CONSTRAINT fk_updates_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaint_supports (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_support_user (complaint_id, user_id),
    INDEX idx_supports_complaint (complaint_id),
    CONSTRAINT fk_supports_complaint FOREIGN KEY (complaint_id)
        REFERENCES complaints(id) ON DELETE CASCADE,
    CONSTRAINT fk_supports_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaint_images (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT UNSIGNED NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    image_type ENUM('complaint', 'progress', 'resolution') NOT NULL DEFAULT 'complaint',
    uploaded_by INT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_images_complaint (complaint_id, image_type),
    CONSTRAINT fk_images_complaint FOREIGN KEY (complaint_id)
        REFERENCES complaints(id) ON DELETE CASCADE,
    CONSTRAINT fk_images_uploader FOREIGN KEY (uploaded_by)
        REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    complaint_id INT UNSIGNED NULL,
    title VARCHAR(180) NOT NULL,
    message VARCHAR(500) NOT NULL,
    type VARCHAR(40) NOT NULL DEFAULT 'info',
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,
    INDEX idx_notifications_user (user_id, is_read, created_at),
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_complaint FOREIGN KEY (complaint_id)
        REFERENCES complaints(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NULL,
    action VARCHAR(120) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id INT UNSIGNED NULL,
    details TEXT NULL,
    ip_address VARCHAR(45) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_created (created_at),
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Demo data. Password for every demo account: Demo@123
-- ---------------------------------------------------------------------------

INSERT IGNORE INTO departments (id, name, code, description, is_active) VALUES
    (1, 'Roads & Infrastructure', 'ROADS', 'Road surfaces, potholes, footpaths and public roads.', 1),
    (2, 'Sanitation', 'SANITATION', 'Waste collection, garbage removal and public cleanliness.', 1),
    (3, 'Water Supply', 'WATER', 'Water leaks, supply pressure and pipeline maintenance.', 1),
    (4, 'Electrical Maintenance', 'ELECTRICAL', 'Street lighting and electrical infrastructure.', 1),
    (5, 'Drainage', 'DRAINAGE', 'Stormwater drains, manholes and flood prevention.', 1),
    (6, 'Public Works', 'PUBLICWORKS', 'Parks, benches and general public infrastructure.', 1);

INSERT IGNORE INTO complaint_categories (id, name, slug, icon, description, is_active) VALUES
    (1, 'Roads & Potholes', 'roads-potholes', 'bi-sign-stop', 'Potholes, cracked roads and damaged footpaths.', 1),
    (2, 'Garbage & Sanitation', 'garbage-sanitation', 'bi-trash', 'Garbage piles, overflowing bins and sanitation.', 1),
    (3, 'Water Leakage', 'water-leakage', 'bi-droplet', 'Leaking pipes, taps and water supply issues.', 1),
    (4, 'Streetlights', 'streetlights', 'bi-lightbulb', 'Broken, flickering or missing street lights.', 1),
    (5, 'Drainage', 'drainage', 'bi-cloud-rain', 'Blocked drains and waterlogging.', 1),
    (6, 'Public Infrastructure', 'public-infrastructure', 'bi-building', 'Damaged public property and amenities.', 1),
    (7, 'Other', 'other', 'bi-three-dots', 'Any other civic issue.', 1);

INSERT IGNORE INTO users (id, full_name, email, phone, password_hash, role, department_id, is_active) VALUES
    (1, 'Aarav Sharma', 'admin@civicfix.demo', '9876500001', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'admin', NULL, 1),
    (2, 'Priya Nair', 'priya@example.demo', '9876500002', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'citizen', NULL, 1),
    (3, 'Rohan Kumar', 'rohan@example.demo', '9876500003', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'citizen', NULL, 1),
    (4, 'Meera Iyer', 'meera@example.demo', '9876500004', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'citizen', NULL, 1),
    (5, 'Arjun Das', 'arjun@example.demo', '9876500005', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'citizen', NULL, 1),
    (6, 'Kavya Reddy', 'kavya@example.demo', '9876500006', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'citizen', NULL, 1),
    (7, 'Suresh Kumar', 'suresh@staff.civicfix.demo', '9876500007', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'staff', 1, 1),
    (8, 'Latha Devi', 'latha@staff.civicfix.demo', '9876500008', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'staff', 2, 1),
    (9, 'Vignesh Raja', 'vignesh@staff.civicfix.demo', '9876500009', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'staff', 3, 1),
    (10, 'Anitha Paul', 'anitha@staff.civicfix.demo', '9876500010', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'staff', 4, 1),
    (11, 'Manikandan M', 'mani@staff.civicfix.demo', '9876500011', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'staff', 5, 1),
    (12, 'Deepa S', 'deepa@staff.civicfix.demo', '9876500012', 'pbkdf2:sha256:260000$ucC0KfrzZ3Z85FUH$9d63095ce2a9086683c30d8bdffd95d0f96fba8900c4374d0136a07c0156f383', 'staff', 6, 1);

INSERT IGNORE INTO complaints (id, tracking_number, citizen_id, category_id, title, description,
    location_address, latitude, longitude, status, priority, suggested_priority, priority_reason,
    is_public, rejection_reason, resolved_at, created_at) VALUES
    (1, 'CFX-2026-00001', 2, 1, 'Deep pothole on MG Road',
     'A deep pothole has formed near the traffic signal. Two-wheelers are swerving into oncoming traffic to avoid it.',
     'MG Road, near Central Signal, Chennai', 13.0827000, 80.2707000, 'Resolved', 'High', 'High',
     'Road safety impact and heavy traffic location.', 1, NULL, '2026-02-04 16:20:00', '2026-01-15 09:30:00'),
    (2, 'CFX-2026-00002', 3, 2, 'Garbage pile near bus stand',
     'Garbage has not been collected for three days and is spilling onto the footpath beside the bus stand.',
     'Central Bus Stand, Chennai', 13.0850000, 80.2750000, 'In Progress', 'Medium', 'Medium',
     'Sanitation issue affecting pedestrians.', 1, NULL, NULL, '2026-01-22 11:15:00'),
    (3, 'CFX-2026-00003', 4, 3, 'Water leakage on Anna Nagar main road',
     'Water is continuously leaking from an underground pipe and pooling on the road.',
     'Anna Nagar Main Road, Chennai', 13.0845000, 80.2780000, 'Assigned', 'High', 'High',
     'Continuous water loss and road damage risk.', 1, NULL, NULL, '2026-02-01 08:45:00'),
    (4, 'CFX-2026-00004', 5, 4, 'Streetlight not working',
     'The streetlight opposite the mosque has been dead for over a week, making the area unsafe at night.',
     'Nadar Street, Chennai', 13.0800000, 80.2720000, 'Verified', 'Medium', 'Medium',
     'Dark spot reported near a residential area.', 1, NULL, NULL, '2026-02-10 18:05:00'),
    (5, 'CFX-2026-00005', 6, 5, 'Drainage blocked during rain',
     'The stormwater drain is completely blocked by plastic waste, causing waterlogging after every rain.',
     'Kodambakkam High Road, Chennai', 13.0860000, 80.2820000, 'Under Review', 'High', 'High',
     'Flooding risk during monsoon season.', 1, NULL, NULL, '2026-02-14 14:35:00'),
    (6, 'CFX-2026-00006', 2, 6, 'Broken bench at neighbourhood park',
     'One of the park benches has broken planks and sharp edges. Children play nearby.',
     'Nehru Park, Chennai', 13.0790000, 80.2680000, 'Submitted', 'Low', 'Low',
     'Non-urgent infrastructure damage with low safety impact.', 1, NULL, NULL, '2026-02-18 10:20:00'),
    (7, 'CFX-2026-00007', 3, 1, 'Road crack widening near school',
     'The road outside the school has developed a wide crack and was patched temporarily. It is reopening.',
     'School Road, Adyar, Chennai', 13.0810000, 80.2740000, 'Reopened', 'High', 'High',
     'School zone safety impact.', 1, NULL, NULL, '2026-02-20 07:55:00'),
    (8, 'CFX-2026-00008', 4, 2, 'Overflowing bins in wholesale market',
     'Garbage bins at the market entrance are overflowing and attracting stray animals.',
     'Wholesale Market, Chennai', 13.0830000, 80.2760000, 'Resolved', 'Medium', 'Medium',
     'Public hygiene concern in a busy market.', 1, NULL, '2026-03-02 12:10:00', '2026-02-22 09:40:00'),
    (9, 'CFX-2026-00009', 5, 3, 'Low water pressure in apartment',
     'Water pressure is low only inside our apartment, which appears to be an internal plumbing issue.',
     'Residential Apartment, Chennai', 13.0870000, 80.2830000, 'Rejected', 'Low', 'Low',
     'Issue appears to be private property plumbing.', 1,
     'The reported low pressure is within internal plumbing, which is outside municipal maintenance scope.', NULL, '2026-02-25 16:00:00'),
    (10, 'CFX-2026-00010', 6, 4, 'Flickering lights at busy junction',
     'Streetlights at the junction flicker and go dark repeatedly, creating a safety hazard for drivers.',
     'Gandhi Road Junction, Chennai', 13.0820000, 80.2690000, 'In Progress', 'Urgent', 'Urgent',
     'Electrical safety risk at a busy junction.', 1, NULL, NULL, '2026-03-01 19:25:00'),
    (11, 'CFX-2026-00011', 2, 5, 'Manhole cover missing',
     'The manhole cover is missing on a busy pedestrian route. A temporary warning was placed by a resident.',
     'Temple Street, Chennai', 13.0880000, 80.2840000, 'Assigned', 'Urgent', 'Urgent',
     'Open manhole poses an immediate safety hazard.', 1, NULL, NULL, '2026-03-05 06:50:00'),
    (12, 'CFX-2026-00012', 3, 7, 'Public fountain out of order',
     'The decorative fountain in the community square has stopped working.',
     'Community Square, Chennai', 13.0900000, 80.2860000, 'Submitted', 'Low', 'Low',
     'Cosmetic issue with no immediate safety impact.', 1, NULL, NULL, '2026-03-08 15:10:00');

INSERT IGNORE INTO complaint_assignments (id, complaint_id, department_id, staff_id, assigned_by, note, is_current, assigned_at) VALUES
    (1, 1, 1, 7, 1, 'Please repair at the earliest.', 1, '2026-01-17 10:00:00'),
    (2, 2, 2, 8, 1, 'Include in the next collection round.', 1, '2026-01-24 09:00:00'),
    (3, 3, 3, 9, 1, 'Inspect the underground line.', 1, '2026-02-03 11:00:00'),
    (4, 4, 4, 10, 1, 'Replace the faulty light.', 1, '2026-02-12 08:30:00'),
    (5, 7, 1, 7, 1, 'Reinspect the temporary patch.', 1, '2026-02-22 10:00:00'),
    (6, 8, 2, 8, 1, 'Clear the bins and schedule regular pickup.', 1, '2026-02-24 09:15:00'),
    (7, 10, 4, 10, 1, 'Urgent electrical inspection required.', 1, '2026-03-02 08:00:00'),
    (8, 11, 5, 11, 1, 'Install a new manhole cover today.', 1, '2026-03-06 07:30:00');

INSERT IGNORE INTO complaint_updates (id, complaint_id, user_id, update_type, from_status, to_status, body, is_public, created_at) VALUES
    (1, 1, 2, 'status', NULL, 'Submitted', 'Complaint submitted with photo evidence.', 1, '2026-01-15 09:30:00'),
    (2, 1, 1, 'status', 'Submitted', 'Under Review', 'Complaint verified by administrator.', 1, '2026-01-16 09:10:00'),
    (3, 1, 1, 'status', 'Under Review', 'Verified', 'Issue confirmed by field inspection.', 1, '2026-01-17 09:45:00'),
    (4, 1, 1, 'status', 'Verified', 'Assigned', 'Assigned to Roads & Infrastructure.', 1, '2026-01-17 10:00:00'),
    (5, 1, 7, 'status', 'Assigned', 'In Progress', 'Road repair crew has arrived on site.', 1, '2026-01-30 08:30:00'),
    (6, 1, 7, 'note', NULL, NULL, 'Removed the damaged patch and prepared the surface.', 1, '2026-02-02 12:00:00'),
    (7, 1, 7, 'status', 'In Progress', 'Resolved', 'Pothole filled and compacted. Site cleaned.', 1, '2026-02-04 16:20:00'),
    (8, 2, 3, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-01-22 11:15:00'),
    (9, 2, 1, 'status', 'Submitted', 'Verified', 'Verified after checking sanitation records.', 1, '2026-01-23 14:00:00'),
    (10, 2, 1, 'status', 'Verified', 'Assigned', 'Assigned to Sanitation department.', 1, '2026-01-24 09:00:00'),
    (11, 2, 8, 'status', 'Assigned', 'In Progress', 'Extra collection vehicle deployed to the area.', 1, '2026-01-28 07:45:00'),
    (12, 3, 4, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-01 08:45:00'),
    (13, 3, 1, 'status', 'Submitted', 'Verified', 'Water board confirmed the leakage.', 1, '2026-02-02 10:00:00'),
    (14, 3, 1, 'status', 'Verified', 'Assigned', 'Assigned to Water Supply department.', 1, '2026-02-03 11:00:00'),
    (15, 4, 5, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-10 18:05:00'),
    (16, 4, 1, 'status', 'Submitted', 'Verified', 'Verified after visual confirmation.', 1, '2026-02-11 09:30:00'),
    (17, 5, 6, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-14 14:35:00'),
    (18, 5, 1, 'status', 'Submitted', 'Under Review', 'Awaiting field inspection.', 1, '2026-02-16 10:00:00'),
    (19, 6, 2, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-18 10:20:00'),
    (20, 7, 3, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-20 07:55:00'),
    (21, 7, 1, 'status', 'Submitted', 'Verified', 'Previous repair found to be inadequate.', 1, '2026-02-21 09:00:00'),
    (22, 7, 1, 'status', 'Verified', 'Assigned', 'Reassigned to Roads & Infrastructure.', 1, '2026-02-22 10:00:00'),
    (23, 7, 3, 'status', 'Assigned', 'Reopened', 'Citizen reported the crack has reappeared.', 1, '2026-03-03 11:30:00'),
    (24, 8, 4, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-22 09:40:00'),
    (25, 8, 8, 'note', NULL, NULL, 'Extra bins placed at the market entrance.', 1, '2026-02-27 15:00:00'),
    (26, 8, 8, 'status', 'In Progress', 'Resolved', 'Market entrance cleaned and bins emptied.', 1, '2026-03-02 12:10:00'),
    (27, 9, 5, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-02-25 16:00:00'),
    (28, 9, 1, 'status', 'Submitted', 'Rejected', 'Private plumbing issue outside municipal scope.', 1, '2026-02-26 09:00:00'),
    (29, 10, 6, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-03-01 19:25:00'),
    (30, 10, 1, 'status', 'Submitted', 'Verified', 'Electrical team confirmed recurring fault.', 1, '2026-03-01 22:00:00'),
    (31, 10, 1, 'status', 'Verified', 'Assigned', 'Assigned to Electrical Maintenance.', 1, '2026-03-02 08:00:00'),
    (32, 10, 10, 'status', 'Assigned', 'In Progress', 'Replacing the faulty wiring and fixtures.', 1, '2026-03-04 09:00:00'),
    (33, 11, 2, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-03-05 06:50:00'),
    (34, 11, 1, 'status', 'Submitted', 'Verified', 'Open manhole confirmed by field team.', 1, '2026-03-05 08:00:00'),
    (35, 11, 1, 'status', 'Verified', 'Assigned', 'Assigned to Drainage department.', 1, '2026-03-06 07:30:00'),
    (36, 12, 3, 'status', NULL, 'Submitted', 'Complaint submitted.', 1, '2026-03-08 15:10:00');

INSERT IGNORE INTO complaint_supports (id, complaint_id, user_id, created_at) VALUES
    (1, 1, 3, '2026-01-16 08:00:00'),
    (2, 1, 4, '2026-01-16 12:00:00'),
    (3, 1, 5, '2026-01-17 08:00:00'),
    (4, 2, 2, '2026-01-23 09:00:00'),
    (5, 2, 6, '2026-01-24 09:00:00'),
    (6, 5, 2, '2026-02-15 10:00:00'),
    (7, 5, 3, '2026-02-16 10:00:00'),
    (8, 7, 5, '2026-02-21 10:00:00'),
    (9, 10, 2, '2026-03-02 10:00:00'),
    (10, 10, 3, '2026-03-02 11:00:00'),
    (11, 11, 4, '2026-03-05 14:00:00'),
    (12, 11, 5, '2026-03-05 15:00:00'),
    (13, 11, 6, '2026-03-06 08:00:00');

INSERT IGNORE INTO notifications (id, user_id, complaint_id, title, message, type, is_read, created_at) VALUES
    (1, 2, 1, 'Complaint submitted', 'Your complaint CFX-2026-00001 was submitted successfully.', 'submitted', 1, '2026-01-15 09:30:00'),
    (2, 2, 1, 'Complaint verified', 'CFX-2026-00001 was verified by an administrator.', 'verified', 1, '2026-01-17 09:45:00'),
    (3, 2, 1, 'Complaint assigned', 'CFX-2026-00001 was assigned to Roads & Infrastructure.', 'assigned', 1, '2026-01-17 10:00:00'),
    (4, 2, 1, 'Work in progress', 'Repair work on CFX-2026-00001 has started.', 'progress', 1, '2026-01-30 08:30:00'),
    (5, 2, 1, 'Complaint resolved', 'CFX-2026-00001 has been resolved. Thank you for reporting.', 'resolved', 1, '2026-02-04 16:20:00'),
    (6, 3, 2, 'Complaint submitted', 'Your complaint CFX-2026-00002 was submitted successfully.', 'submitted', 1, '2026-01-22 11:15:00'),
    (7, 3, 2, 'Work in progress', 'Collection work on CFX-2026-00002 has started.', 'progress', 0, '2026-01-28 07:45:00'),
    (8, 4, 3, 'Complaint assigned', 'CFX-2026-00003 was assigned to Water Supply.', 'assigned', 0, '2026-02-03 11:00:00'),
    (9, 5, 4, 'Complaint verified', 'CFX-2026-00004 was verified by an administrator.', 'verified', 1, '2026-02-11 09:30:00'),
    (10, 6, 5, 'Complaint submitted', 'Your complaint CFX-2026-00005 was submitted successfully.', 'submitted', 1, '2026-02-14 14:35:00'),
    (11, 6, 5, 'Under review', 'CFX-2026-00005 is now under review.', 'review', 0, '2026-02-16 10:00:00'),
    (12, 7, 1, 'New assignment', 'Complaint CFX-2026-00001 was assigned to you.', 'assignment', 1, '2026-01-17 10:00:00'),
    (13, 8, 2, 'New assignment', 'Complaint CFX-2026-00002 was assigned to you.', 'assignment', 1, '2026-01-24 09:00:00'),
    (14, 9, 3, 'New assignment', 'Complaint CFX-2026-00003 was assigned to you.', 'assignment', 0, '2026-02-03 11:00:00'),
    (15, 10, 10, 'Priority changed', 'Complaint CFX-2026-00010 priority was set to Urgent.', 'priority', 0, '2026-03-02 08:05:00'),
    (16, 11, 11, 'New assignment', 'Complaint CFX-2026-00011 was assigned to you.', 'assignment', 0, '2026-03-06 07:30:00'),
    (17, 3, 7, 'Complaint reopened', 'CFX-2026-00007 was reopened after your update.', 'reopened', 0, '2026-03-03 11:30:00'),
    (18, 5, 9, 'Complaint rejected', 'CFX-2026-00009 was rejected. Check the admin note for details.', 'rejected', 0, '2026-02-26 09:00:00');

INSERT IGNORE INTO audit_logs (id, user_id, action, entity_type, entity_id, details, ip_address, created_at) VALUES
    (1, 1, 'verified_complaint', 'complaint', 1, 'Status changed from Submitted to Under Review', '127.0.0.1', '2026-01-16 09:10:00'),
    (2, 1, 'assigned_complaint', 'complaint', 1, 'Assigned to department 1 and staff 7', '127.0.0.1', '2026-01-17 10:00:00'),
    (3, 7, 'updated_status', 'complaint', 1, 'In Progress to Resolved', '127.0.0.1', '2026-02-04 16:20:00'),
    (4, 1, 'rejected_complaint', 'complaint', 9, 'Private plumbing issue', '127.0.0.1', '2026-02-26 09:00:00'),
    (5, 1, 'changed_priority', 'complaint', 10, 'Medium to Urgent', '127.0.0.1', '2026-03-02 08:00:00');
