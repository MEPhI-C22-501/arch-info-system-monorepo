package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.collaboration.Attachment;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface AttachmentRepository {
    /** Metadata only (no bytea content) — matches the old list query's shape. */
    List<Attachment> findMetadataByWorkItem(UUID workItemId);

    /** Throws ApiException.missing("attachmentId") if not found under that work item. Includes content. */
    Attachment getByIdAndWorkItem(UUID id, UUID workItemId);

    Optional<Attachment> findByIdAndWorkItem(UUID id, UUID workItemId);

    void insert(Attachment attachment);

    void delete(UUID id);
}
