CREATE DATABASE IF NOT EXISTS nyc_payroll;
USE nyc_payroll;

DROP TABLE IF EXISTS payroll_records;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS agencies;
DROP TABLE IF EXISTS job_titles;
DROP TABLE IF EXISTS work_locations;
DROP TABLE IF EXISTS fiscal_years;

CREATE TABLE agencies (
    agency_id INT PRIMARY KEY,
    agency_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE job_titles (
    title_id INT PRIMARY KEY,
    title_description VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE work_locations (
    location_id INT PRIMARY KEY,
    work_location_borough VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE fiscal_years (
    fiscal_year_id INT PRIMARY KEY,
    fiscal_year INT NOT NULL UNIQUE,
    CHECK (fiscal_year BETWEEN 2000 AND 2100)
);

CREATE TABLE employees (
    employee_id INT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    middle_initial VARCHAR(10),
    agency_start_date DATE
);

CREATE TABLE payroll_records (
    payroll_record_id BIGINT PRIMARY KEY,

    employee_id INT NOT NULL,
    agency_id INT NOT NULL,
    title_id INT NOT NULL,
    location_id INT NOT NULL,
    fiscal_year_id INT NOT NULL,

    leave_status VARCHAR(100),
    base_salary DECIMAL(14,2),
    pay_basis VARCHAR(50),
    regular_hours DECIMAL(10,2),
    regular_gross_paid DECIMAL(14,2),
    overtime_hours DECIMAL(10,2),
    total_overtime_paid DECIMAL(14,2),
    total_other_pay DECIMAL(14,2),
    total_compensation DECIMAL(14,2),
    overtime_pay_share DECIMAL(10,6),
    total_hours DECIMAL(10,2),
    overtime_hours_share DECIMAL(10,6),

    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (agency_id) REFERENCES agencies(agency_id),
    FOREIGN KEY (title_id) REFERENCES job_titles(title_id),
    FOREIGN KEY (location_id) REFERENCES work_locations(location_id),
    FOREIGN KEY (fiscal_year_id) REFERENCES fiscal_years(fiscal_year_id)
);
);

CREATE INDEX idx_payroll_employee ON payroll_records(employee_id);
CREATE INDEX idx_payroll_agency ON payroll_records(agency_id);
CREATE INDEX idx_payroll_title ON payroll_records(title_id);
CREATE INDEX idx_payroll_fiscal_year ON payroll_records(fiscal_year_id);
CREATE INDEX idx_payroll_location ON payroll_records(location_id);
CREATE INDEX idx_payroll_overtime_paid ON payroll_records(total_overtime_paid);
CREATE INDEX idx_payroll_total_compensation ON payroll_records(total_compensation);