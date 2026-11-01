package ru.mephi.arch.tasktracker.domain.workitem;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Plain mutable entity — fields are public on purpose (matches this codebase's low-ceremony style;
 * see CLAUDE.md). {@code type} and the testing-service provenance fields never change after
 * creation, everything else can; {@link #applyFieldUpdate} and {@link #touch} are the only ways the
 * mutable fields and {@code version}/{@code updatedAt} move, so every write path is traceable.
 */
public final class WorkItem {
    public final UUID id;
    public final WorkItemType type;
    public String title;
    public String description;
    public UUID statusId;
    public UUID priorityId;
    public String assigneeId;
    public LocalDate startDate;
    public LocalDate dueDate;
    public BigDecimal plannedHours;
    public UUID parentId;
    public final String externalSource;
    public final String externalDefectId;
    public final String severity;
    public final String environment;
    public final String testRunUrl;
    public final String testCaseUrl;
    public long version;
    public final OffsetDateTime createdAt;
    public OffsetDateTime updatedAt;

    public WorkItem(UUID id, WorkItemType type, String title, String description, UUID statusId, UUID priorityId,
                     String assigneeId, LocalDate startDate, LocalDate dueDate, BigDecimal plannedHours, UUID parentId,
                     String externalSource, String externalDefectId, String severity, String environment,
                     String testRunUrl, String testCaseUrl, long version, OffsetDateTime createdAt, OffsetDateTime updatedAt) {
        this.id = id; this.type = type; this.title = title; this.description = description;
        this.statusId = statusId; this.priorityId = priorityId; this.assigneeId = assigneeId;
        this.startDate = startDate; this.dueDate = dueDate; this.plannedHours = plannedHours; this.parentId = parentId;
        this.externalSource = externalSource; this.externalDefectId = externalDefectId; this.severity = severity;
        this.environment = environment; this.testRunUrl = testRunUrl; this.testCaseUrl = testCaseUrl;
        this.version = version; this.createdAt = createdAt; this.updatedAt = updatedAt;
    }

    public void applyFieldUpdate(String title, String description, UUID statusId, UUID priorityId, String assigneeId,
                                  LocalDate startDate, LocalDate dueDate, BigDecimal plannedHours, UUID parentId,
                                  OffsetDateTime now) {
        this.title = title; this.description = description; this.statusId = statusId; this.priorityId = priorityId;
        this.assigneeId = assigneeId; this.startDate = startDate; this.dueDate = dueDate; this.plannedHours = plannedHours;
        this.parentId = parentId; this.updatedAt = now; this.version++;
    }

    /** Bumps version/updatedAt without changing any field — used on a parent when a child is added/removed/re-estimated. */
    public void touch(OffsetDateTime now) { this.updatedAt = now; this.version++; }

    public record ChildSummary(UUID id, WorkItemType type, String title, UUID statusId) {}
}
