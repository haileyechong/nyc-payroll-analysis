USE nyc_payroll;
-- 1. Which NYC Agencies spend the most total money on overtime pay?
SELECT a.agency_name,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_spending,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
    JOIN agencies a ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
ORDER BY total_overtime_spending DESC
LIMIT 15;
-- 2. Which agencies rely on overtime compared to regular gross pay?
SELECT a.agency_name,
    ROUND(SUM(pr.regular_gross_paid), 2) AS total_regular_gross_paid,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
    ROUND(
        SUM(pr.total_overtime_paid) / NULLIF(SUM(pr.regular_gross_paid), 0),
        4
    ) AS overtime_to_regular_pay_ratio
FROM payroll_records pr
    JOIN agencies a ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
HAVING COUNT(*) >= 100
ORDER BY overtime_to_regular_pay_ratio DESC
LIMIT 15;
-- 3. How many estimated employees does each agency have, and how much does each agency spend on total compensation?
SELECT a.agency_name,
    COUNT(DISTINCT pr.employee_id) AS estimated_employee_count,
    COUNT(*) AS payroll_record_count,
    ROUND(SUM(pr.total_compensation), 2) AS total_compensation_spending,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation
FROM payroll_records pr
    JOIN agencies a ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
ORDER BY total_compensation_spending DESC
LIMIT 15;
-- 4. How have payroll spending and overtime spending changed across fiscal years?
SELECT fy.fiscal_year,
    ROUND(SUM(pr.total_compensation), 2) AS total_compensation_spending,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_spending,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid
FROM payroll_records pr
    JOIN fiscal_years fy ON pr.fiscal_year_id = fy.fiscal_year_id
GROUP BY fy.fiscal_year
ORDER BY fy.fiscal_year;
-- 5. Which job titles have the highest overtime hours relative to regular hours?
SELECT jt.title_description,
    ROUND(SUM(pr.regular_hours), 2) AS total_regular_hours,
    ROUND(SUM(pr.overtime_hours), 2) AS total_overtime_hours,
    ROUND(
        SUM(pr.overtime_hours) / NULLIF(SUM(pr.regular_hours), 0),
        4
    ) AS overtime_to_regular_hours_ratio,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
    JOIN job_titles jt ON pr.title_id = jt.title_id
GROUP BY jt.title_description
HAVING COUNT(*) >= 100
ORDER BY overtime_to_regular_hours_ratio DESC
LIMIT 15;
-- 6. Which job titles have the highest average total compensation?
SELECT jt.title_description,
    ROUND(AVG(pr.base_salary), 2) AS avg_base_salary,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation,
    ROUND(AVG(pr.total_compensation - pr.base_salary), 2) AS avg_extra_compensation,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
    JOIN job_titles jt ON pr.title_id = jt.title_id
GROUP BY jt.title_description
HAVING COUNT(*) >= 100
ORDER BY avg_total_compensation DESC
LIMIT 15;
-- 7. How does total compensation differ by work location borough?
SELECT wl.work_location_borough,
    COUNT(*) AS payroll_record_count,
    ROUND(AVG(pr.base_salary), 2) AS avg_base_salary,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid
FROM payroll_records pr
    JOIN work_locations wl ON pr.location_id = wl.location_id
GROUP BY wl.work_location_borough
ORDER BY avg_total_compensation DESC;
-- 8. Which individual payroll records had unusually high overtime pay?
SELECT pr.payroll_record_id,
    a.agency_name,
    jt.title_description,
    wl.work_location_borough,
    pr.base_salary,
    pr.regular_gross_paid,
    pr.overtime_hours,
    pr.total_overtime_paid,
    pr.total_compensation
FROM payroll_records pr
    JOIN agencies a ON pr.agency_id = a.agency_id
    JOIN job_titles jt ON pr.title_id = jt.title_id
    JOIN work_locations wl ON pr.location_id = wl.location_id
WHERE pr.total_overtime_paid >= 50000
ORDER BY pr.total_overtime_paid DESC
LIMIT 25;
-- 9. Which agencies have the largest average difference between base salary and actual total compensation?
SELECT a.agency_name,
    ROUND(AVG(pr.base_salary), 2) AS avg_base_salary,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation,
    ROUND(AVG(pr.total_compensation - pr.base_salary), 2) AS avg_pay_gap,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
    JOIN agencies a ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
HAVING COUNT(*) >= 100
ORDER BY avg_pay_gap DESC
LIMIT 15;