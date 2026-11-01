package ru.mephi.arch.tasktracker.application.port;

import java.time.OffsetDateTime;
import java.util.UUID;

public interface NotificationRepository {
    /** {@code workItemId} is nullable — null means the item was hard-deleted; the snapshot
     * ({@code workItemPublicId}/{@code title}) is what keeps the notification meaningful either way. */
    void create(String recipientId, UUID workItemId, String workItemPublicId, String title,
                String message, String actor, OffsetDateTime createdAt);
}
