package ru.mephi.arch.tasktracker.domain.event;

import java.util.Map;
import java.util.UUID;

/** Raised against the PARENT item when a child is added or removed — matches today's "Изменена иерархия" audit entry. */
public record HierarchyChanged(UUID workItemId, String actorId, String source,
                                Map<String, Object> oldValues, Map<String, Object> newValues)
    implements RecordableChange {
    @Override public String message() { return "Изменена иерархия"; }
}
