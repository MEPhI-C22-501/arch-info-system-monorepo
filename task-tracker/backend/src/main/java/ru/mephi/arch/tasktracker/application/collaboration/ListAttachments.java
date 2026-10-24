package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.AttachmentRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ListAttachments {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final AttachmentRepository attachments;
    public ListAttachments(WorkItemRepository workItems, PermissionPort permissions, AttachmentRepository attachments) {
        this.workItems = workItems; this.permissions = permissions; this.attachments = attachments;
    }

    public List<Map<String, Object>> execute(UUID workItemId) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        return attachments.findMetadataByWorkItem(workItemId).stream()
            .<Map<String, Object>>map(a -> Map.of("id", a.id, "fileName", a.fileName, "sizeBytes", a.sizeBytes,
                "contentType", a.contentType, "uploadedById", a.uploadedByExternalId, "uploadedAt", a.uploadedAt))
            .toList();
    }
}
