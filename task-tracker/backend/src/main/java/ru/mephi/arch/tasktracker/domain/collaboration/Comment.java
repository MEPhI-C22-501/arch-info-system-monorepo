package ru.mephi.arch.tasktracker.domain.collaboration;

import java.time.OffsetDateTime;
import java.util.UUID;

public final class Comment {
    public final UUID id;
    public final UUID workItemId;
    public final String authorExternalId;
    public String body;
    public final OffsetDateTime createdAt;

    public Comment(UUID id, UUID workItemId, String authorExternalId, String body, OffsetDateTime createdAt) {
        this.id = id; this.workItemId = workItemId; this.authorExternalId = authorExternalId;
        this.body = body; this.createdAt = createdAt;
    }
}
