USE nyc_payroll;


-- Query 1
-- Which NYC agencies spend the most total money on overtime pay?

SELECT 
    a.agency_name,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_spending,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
JOIN agencies a 
    ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
ORDER BY total_overtime_spending DESC
LIMIT 15;



-- Query 2
-- Which agencies rely most heavily on overtime compared to regular gross pay?


SELECT 
    a.agency_name,
    ROUND(SUM(pr.regular_gross_paid), 2) AS total_regular_gross_paid,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
    ROUND(
        SUM(pr.total_overtime_paid) / NULLIF(SUM(pr.regular_gross_paid), 0),
        4
    ) AS overtime_to_regular_pay_ratio
FROM payroll_records pr
JOIN agencies a 
    ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
HAVING 
    COUNT(*) >= 100
    AND SUM(pr.regular_gross_paid) > 0
ORDER BY overtime_to_regular_pay_ratio DESC
LIMIT 15;


-- Query 3
-- and how much does each agency spend on total compensation?

SELECT 
    a.agency_name,
    COUNT(DISTINCT pr.employee_id) AS estimated_employee_count,
    COUNT(*) AS payroll_record_count,
    ROUND(SUM(pr.total_compensation), 2) AS total_compensation_spending,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation
FROM payroll_records pr
JOIN agencies a 
    ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
ORDER BY total_compensation_spending DESC
LIMIT 15;


-- Query 4
-- How have payroll spending and overtime spending changed across fiscal years?

SELECT 
    fy.fiscal_year,
    ROUND(SUM(pr.total_compensation), 2) AS total_compensation_spending,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_spending,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid
FROM payroll_records pr
JOIN fiscal_years fy 
    ON pr.fiscal_year_id = fy.fiscal_year_id
GROUP BY fy.fiscal_year
ORDER BY fy.fiscal_year;


-- Query 5
-- Which job titles have the highest average overtime pay?

SELECT 
    jt.title_description,
    COUNT(*) AS payroll_record_count,
    COUNT(DISTINCT pr.employee_id) AS estimated_employee_count,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid,
    ROUND(AVG(pr.overtime_hours), 2) AS avg_overtime_hours
FROM payroll_records pr
JOIN job_titles jt
    ON pr.title_id = jt.title_id
GROUP BY jt.title_description
HAVING 
    COUNT(*) >= 100
    AND SUM(pr.total_overtime_paid) > 0
ORDER BY avg_overtime_paid DESC
LIMIT 15;


-- Query 6
-- Which annual-salary job titles have the highest average total compensation?


SELECT 
    jt.title_description,
    ROUND(AVG(pr.base_salary), 2) AS avg_base_salary,
    ROUND(AVG(pr.total_compensation), 2) AS avg_total_compensation,
    ROUND(AVG(pr.total_compensation - pr.base_salary), 2) AS avg_extra_compensation,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
JOIN job_titles jt 
    ON pr.title_id = jt.title_id
WHERE 
    pr.pay_basis = 'PER ANNUM'
GROUP BY jt.title_description
HAVING COUNT(*) >= 100
ORDER BY avg_total_compensation DESC
LIMIT 15;


-- Query 7
-- Which individual payroll records had unusually high overtime pay
-- and recorded overtime hours?

SELECT 
    pr.payroll_record_id,
    a.agency_name,
    jt.title_description,
    wl.work_location_borough,
    pr.base_salary,
    pr.regular_gross_paid,
    pr.overtime_hours,
    pr.total_overtime_paid,
    pr.total_compensation
FROM payroll_records pr
JOIN agencies a 
    ON pr.agency_id = a.agency_id
JOIN job_titles jt 
    ON pr.title_id = jt.title_id
JOIN work_locations wl 
    ON pr.location_id = wl.location_id
WHERE 
    pr.total_overtime_paid >= 50000
    AND pr.overtime_hours > 0
ORDER BY pr.total_overtime_paid DESC
LIMIT 25;


-- Query 8
-- Business question:
-- Which estimated employees earned the most in overtime pay?
-- Note: employee_id is estimated from name/start-date fields.

SELECT 
    e.employee_id,
    e.first_name,
    e.last_name,
    e.middle_initial,
    e.agency_start_date,
    a.agency_name,
    jt.title_description,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
    ROUND(SUM(pr.overtime_hours), 2) AS total_overtime_hours,
    COUNT(*) AS payroll_record_count
FROM payroll_records pr
JOIN employees e
    ON pr.employee_id = e.employee_id
JOIN agencies a
    ON pr.agency_id = a.agency_id
JOIN job_titles jt
    ON pr.title_id = jt.title_id
GROUP BY 
    e.employee_id,
    e.first_name,
    e.last_name,
    e.middle_initial,
    e.agency_start_date,
    a.agency_name,
    jt.title_description
HAVING SUM(pr.total_overtime_paid) > 0
ORDER BY total_overtime_paid DESC
LIMIT 25;



-- Query 9
-- Which agencies have the highest overtime-to-headcount ratio?
-- This measures overtime spending per estimated employee.


SELECT 
    a.agency_name,
    COUNT(DISTINCT pr.employee_id) AS estimated_employee_count,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
    ROUND(SUM(pr.overtime_hours), 2) AS total_overtime_hours,
    ROUND(
        SUM(pr.total_overtime_paid) / NULLIF(COUNT(DISTINCT pr.employee_id), 0),
        2
    ) AS overtime_pay_per_estimated_employee,
    ROUND(
        SUM(pr.overtime_hours) / NULLIF(COUNT(DISTINCT pr.employee_id), 0),
        2
    ) AS overtime_hours_per_estimated_employee
FROM payroll_records pr
JOIN agencies a
    ON pr.agency_id = a.agency_id
GROUP BY a.agency_name
HAVING COUNT(DISTINCT pr.employee_id) >= 100
ORDER BY overtime_pay_per_estimated_employee DESC
LIMIT 15;



-- Query 10
-- Which job titles have the highest average overtime pay?

SELECT 
    jt.title_description,
    COUNT(*) AS payroll_record_count,
    COUNT(DISTINCT pr.employee_id) AS estimated_employee_count,
    ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
    ROUND(AVG(pr.total_overtime_paid), 2) AS avg_overtime_paid,
    ROUND(AVG(pr.overtime_hours), 2) AS avg_overtime_hours
FROM payroll_records pr
JOIN job_titles jt
    ON pr.title_id = jt.title_id
GROUP BY jt.title_description
HAVING 
    COUNT(*) >= 100
    AND SUM(pr.total_overtime_paid) > 0
ORDER BY avg_overtime_paid DESC
LIMIT 15;



-- Query 11
-- Which records have unusually low overtime pay relative to
-- estimated regular hourly pay?
--
-- This is an anomaly-style query, not a legal conclusion.
-- It estimates:
-- regular hourly rate = regular_gross_paid / regular_hours
-- actual OT hourly rate = total_overtime_paid / overtime_hours
-- expected OT hourly rate = estimated regular hourly rate * 1.5


SELECT 
    pr.payroll_record_id,
    e.employee_id,
    e.first_name,
    e.last_name,
    a.agency_name,
    jt.title_description,
    pr.pay_basis,
    ROUND(pr.regular_hours, 2) AS regular_hours,
    ROUND(pr.overtime_hours, 2) AS overtime_hours,
    ROUND(pr.regular_gross_paid, 2) AS regular_gross_paid,
    ROUND(pr.total_overtime_paid, 2) AS total_overtime_paid,

    ROUND(
        pr.regular_gross_paid / NULLIF(pr.regular_hours, 0),
        2
    ) AS estimated_regular_hourly_rate,

    ROUND(
        pr.total_overtime_paid / NULLIF(pr.overtime_hours, 0),
        2
    ) AS actual_overtime_hourly_rate,

    ROUND(
        (pr.regular_gross_paid / NULLIF(pr.regular_hours, 0)) * 1.5,
        2
    ) AS estimated_expected_overtime_rate,

    ROUND(
        (pr.total_overtime_paid / NULLIF(pr.overtime_hours, 0))
        / NULLIF((pr.regular_gross_paid / NULLIF(pr.regular_hours, 0)) * 1.5, 0),
        4
    ) AS actual_to_expected_overtime_ratio

FROM payroll_records pr
JOIN employees e
    ON pr.employee_id = e.employee_id
JOIN agencies a
    ON pr.agency_id = a.agency_id
JOIN job_titles jt
    ON pr.title_id = jt.title_id
WHERE
    pr.regular_hours >= 100
    AND pr.overtime_hours >= 10
    AND pr.regular_gross_paid > 0
    AND pr.total_overtime_paid > 0
    AND pr.pay_basis = 'PER ANNUM'
    AND (
        pr.total_overtime_paid / NULLIF(pr.overtime_hours, 0)
    ) < (
        pr.regular_gross_paid / NULLIF(pr.regular_hours, 0)
    ) * 1.5
ORDER BY actual_to_expected_overtime_ratio ASC
LIMIT 25;