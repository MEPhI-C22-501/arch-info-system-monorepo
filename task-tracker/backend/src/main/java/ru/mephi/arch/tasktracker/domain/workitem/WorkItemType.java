package ru.mephi.arch.tasktracker.domain.workitem;

import ru.mephi.arch.tasktracker.ApiException;

public enum WorkItemType {
    PROJECT, EPIC, TASK, BUG, SUBTASK;

    public static WorkItemType from(String value) {
        if (value == null) throw ApiException.invalid("type", "invalid_type");
        try { return WorkItemType.valueOf(value); }
        catch (IllegalArgumentException e) { throw ApiException.invalid("type", "invalid_type"); }
    }

    /** EPIC/SUBTASK must have a parent; PROJECT/TASK/BUG don't require one. */
    public boolean requiresParent() { return this == EPIC || this == SUBTASK; }

    /** PROJECT/EPIC have their plannedHours computed from leaf descendants, never set directly. */
    public boolean allowsPlannedHoursDirectly() { return this != PROJECT && this != EPIC; }

    public boolean isValidChildOf(WorkItemType parentType) {
        return switch (this) {
            case EPIC -> parentType == PROJECT;
            case TASK, BUG -> parentType == EPIC;
            case SUBTASK -> parentType == TASK || parentType == BUG;
            case PROJECT -> false;
        };
    }
}
