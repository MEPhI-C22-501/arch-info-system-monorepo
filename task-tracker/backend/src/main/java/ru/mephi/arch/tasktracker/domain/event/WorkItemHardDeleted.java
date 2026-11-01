package ru.mephi.arch.tasktracker.domain.event;

/**
 * No audit entry is raised for this one — the row (and any audit_entry pointing at it) is already
 * gone by the time this is published, matching today's behavior exactly. Only a notification with a
 * denormalized snapshot survives, which is why this doesn't implement {@link RecordableChange}.
 */
public record WorkItemHardDeleted(String recipientId, String workItemPublicId, String title, String actorId)
    implements DomainEvent {
}
