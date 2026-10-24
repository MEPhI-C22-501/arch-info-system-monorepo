package ru.mephi.arch.tasktracker.domain.collaboration;

import java.time.OffsetDateTime;
import java.util.UUID;

public final class Attachment {
    public final UUID id;
    public final UUID workItemId;
    public final String fileName;
    public final long sizeBytes;
    public final String contentType;
    public final byte[] content;
    public final String uploadedByExternalId;
    public final OffsetDateTime uploadedAt;

    public Attachment(UUID id, UUID workItemId, String fileName, long sizeBytes, String contentType, byte[] content,
                       String uploadedByExternalId, OffsetDateTime uploadedAt) {
        this.id = id; this.workItemId = workItemId; this.fileName = fileName; this.sizeBytes = sizeBytes;
        this.contentType = contentType; this.content = content; this.uploadedByExternalId = uploadedByExternalId;
        this.uploadedAt = uploadedAt;
    }
}
