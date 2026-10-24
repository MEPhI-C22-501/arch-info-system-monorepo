package ru.mephi.arch.tasktracker.domain.event;

import java.util.Map;
import java.util.UUID;

/** Recorded against the work item, not the iteration — matches the old behavior exactly:
 * {@code workItemId} is the item added/removed, so it shows up in that item's own history. */
public record IterationCompositionChanged(UUID workItemId, String actorId, String source,
                                           Map<String, Object> oldValues, Map<String, Object> newValues, String message)
    implements RecordableChange {
}
