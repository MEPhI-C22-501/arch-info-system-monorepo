package ru.mephi.arch.tasktracker.domain.workitem;

import ru.mephi.arch.tasktracker.ApiException;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Validates the 5-type hierarchy and date/estimate rules — pure, no IO. The use case resolves the
 * parent (if {@code parentId} is set, fetching it first — a 404 there means the parent doesn't
 * exist, not an invalid-hierarchy 422) and whether the item already has children before calling in.
 */
public final class WorkItemFactory {
    private WorkItemFactory() {}

    public static WorkItem create(UUID id, WorkItemType type, String title, String description, UUID statusId,
                                   UUID priorityId, String assigneeId, LocalDate startDate, LocalDate dueDate,
                                   BigDecimal plannedHours, UUID parentId, WorkItem parent,
                                   String externalSource, String externalDefectId, String severity, String environment,
                                   String testRunUrl, String testCaseUrl, OffsetDateTime now) {
        validateParentage(id, type, parentId, parent);
        validateDates(startDate, dueDate);
        validatePlannedHoursAllowed(type, plannedHours);
        return new WorkItem(id, type, title, description, statusId, priorityId, assigneeId, startDate, dueDate,
            plannedHours, parentId, externalSource, externalDefectId, severity, environment, testRunUrl, testCaseUrl,
            0L, now, now);
    }

    /** {@code parent} must be non-null whenever {@code parentId} is non-null — the caller resolves it first. */
    public static void validateParentage(UUID id, WorkItemType type, UUID parentId, WorkItem parent) {
        if (parentId == null) {
            if (type.requiresParent()) throw ApiException.invalid("parentId", "required_for_type");
            return;
        }
        if (parentId.equals(id)) throw ApiException.invalid("parentId", "self_parent");
        if (!type.isValidChildOf(parent.type)) throw ApiException.invalid("parentId", "invalid_hierarchy");
    }

    public static void validateDates(LocalDate startDate, LocalDate dueDate) {
        if (startDate != null && dueDate != null && dueDate.isBefore(startDate)) {
            throw ApiException.invalid("dueDate", "before_start_date");
        }
    }

    public static void validatePlannedHoursAllowed(WorkItemType type, BigDecimal plannedHours) {
        if (plannedHours != null && !type.allowsPlannedHoursDirectly()) {
            throw ApiException.invalid("plannedHours", "parent_is_computed");
        }
    }
}
