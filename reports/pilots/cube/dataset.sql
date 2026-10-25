SELECT "userId" AS user_id,
       "projectId" AS project_id,
       DATE_TRUNC('day', "loggedDate") AS logged_date,
       SUM("hours") AS hours
FROM "TimeLogs"
GROUP BY 1, 2, 3
