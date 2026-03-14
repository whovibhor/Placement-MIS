-- Run this script once to set up the database and table.
-- Or let the Flask app create it automatically on first run.
CREATE DATABASE IF NOT EXISTS placement_mis;

USE placement_mis;

CREATE TABLE IF NOT EXISTS students (
    sr_no INT,
    reg_no VARCHAR(50) PRIMARY KEY,
    student_name VARCHAR(200),
    gender VARCHAR(20),
    course VARCHAR(100),
    resume_status VARCHAR(100),
    seeking_placement VARCHAR(100),
    department VARCHAR(100),
    offer_letter_status VARCHAR(100),
    status VARCHAR(100),
    company_name VARCHAR(200),
    designation VARCHAR(200),
    ctc VARCHAR(100),
    joining_date VARCHAR(100),
    joining_status VARCHAR(100),
    school_name VARCHAR(200),
    mobile_number VARCHAR(50),
    email VARCHAR(200),
    graduation_course VARCHAR(100),
    graduation_ogpa VARCHAR(50),
    percent_10 VARCHAR(50),
    percent_12 VARCHAR(50),
    backlogs VARCHAR(50),
    hometown VARCHAR(200),
    address TEXT,
    reason TEXT
);