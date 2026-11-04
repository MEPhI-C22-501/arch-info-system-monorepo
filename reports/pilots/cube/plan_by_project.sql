-- R-06 plan side: plan and remaining hours of the current tasks per project (ADR-018).
SELECT "projectId" AS project_id,
       MEASURE("plannedHours") AS planned_hours,
       MEASURE("remainingHours") AS remaining_hours,
       MEASURE("tasks") AS tasks
FROM "WorkItems"
GROUP BY 1
