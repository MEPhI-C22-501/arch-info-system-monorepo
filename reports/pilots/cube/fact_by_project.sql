-- R-06 fact side: logged hours per project and day; the dashboard filter sets the period.
SELECT "projectId" AS project_id,
       DATE_TRUNC('day', "loggedDate") AS logged_date,
       SUM("hours") AS hours
FROM "TimeLogs"
GROUP BY 1, 2
