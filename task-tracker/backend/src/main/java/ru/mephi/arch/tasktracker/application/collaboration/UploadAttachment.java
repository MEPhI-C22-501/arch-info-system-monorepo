package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.AttachmentRepository;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.Attachment;
import ru.mephi.arch.tasktracker.domain.event.AttachmentChanged;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class UploadAttachment {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final AttachmentRepository attachments;
    private final EventPublisherPort events;
    private final long maxBytes;

    public UploadAttachment(WorkItemRepository workItems, PermissionPort permissions, AttachmentRepository attachments,
                             EventPublisherPort events, @org.springframework.beans.factory.annotation.Value("${app.attachment-max-bytes}") long maxBytes) {
        this.workItems = workItems; this.permissions = permissions; this.attachments = attachments;
        this.events = events; this.maxBytes = maxBytes;
    }

    @Transactional
    public Map<String, Object> execute(UUID workItemId, MultipartFile file) throws IOException {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        permissions.require("attachment.create");
        if (file.isEmpty() || file.getSize() > maxBytes) throw ApiException.invalid("file", "empty_or_too_large");
        UUID id = UUID.randomUUID();
        String name = Optional.ofNullable(file.getOriginalFilename()).orElse("attachment").replaceAll("[\\r\\n/\\\\]", "_");
        String type = Optional.ofNullable(file.getContentType()).orElse("application/octet-stream");
        String actor = permissions.currentSubject();
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        attachments.insert(new Attachment(id, workItemId, name, file.getSize(), type, file.getBytes(), actor, now));
        workItems.touch(workItemId);
        events.publish(new AttachmentChanged(workItemId, actor, null, Map.of("attachmentAdded", false),
            Map.of("attachmentAdded", id.toString()), "Добавлен файл"));
        return Map.of("id", id, "fileName", name, "sizeBytes", file.getSize(), "contentType", type, "uploadedById", actor, "uploadedAt", now);
    }
}
