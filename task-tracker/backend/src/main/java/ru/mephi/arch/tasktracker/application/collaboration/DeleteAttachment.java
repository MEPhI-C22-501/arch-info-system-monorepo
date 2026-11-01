package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.AttachmentRepository;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.Attachment;
import ru.mephi.arch.tasktracker.domain.event.AttachmentChanged;

import java.util.Map;
import java.util.UUID;

@Service
public class DeleteAttachment {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final AttachmentRepository attachments;
    private final EventPublisherPort events;
    public DeleteAttachment(WorkItemRepository workItems, PermissionPort permissions, AttachmentRepository attachments, EventPublisherPort events) {
        this.workItems = workItems; this.permissions = permissions; this.attachments = attachments; this.events = events;
    }

    @Transactional
    public void execute(UUID workItemId, UUID attachmentId) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        permissions.require("attachment.delete");
        Attachment attachment = attachments.getByIdAndWorkItem(attachmentId, workItemId);
        if ("MEMBER".equals(permissions.currentRole()) && !permissions.currentSubject().equals(attachment.uploadedByExternalId)) {
            throw new ApiException(403, "attachment", "forbidden");
        }
        attachments.delete(attachmentId);
        workItems.touch(workItemId);
        events.publish(new AttachmentChanged(workItemId, permissions.currentSubject(), null,
            Map.of("attachmentRemoved", false), Map.of("attachmentRemoved", attachmentId.toString()), "Удалён файл"));
    }
}
