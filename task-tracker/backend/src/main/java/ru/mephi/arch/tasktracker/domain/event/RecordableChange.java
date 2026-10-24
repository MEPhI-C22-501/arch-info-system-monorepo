package ru.mephi.arch.tasktracker.domain.event;

import java.util.Map;
import java.util.UUID;

/**
 * A change that must be diffed into an audit entry and, if the item has an assignee, turned into a
 * notification — the two steps {@code ChangeRecorder.record} used to do inline. {@code oldValues}/
 * {@code newValues} are the full before/after field maps; listeners compute the actual diff, exactly
 * like {@code ChangeRecorder} did, so a no-op update still raises nothing persisted.
 */
public interface RecordableChange extends DomainEvent {
    UUID workItemId();
    String actorId();
    String source();
    Map<String, Object> oldValues();
    Map<String, Object> newValues();
    String message();
}
