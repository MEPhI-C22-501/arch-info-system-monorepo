package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.AttachmentRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

@Service
public class DownloadAttachment {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final AttachmentRepository attachments;
    public DownloadAttachment(WorkItemRepository workItems, PermissionPort permissions, AttachmentRepository attachments) {
        this.workItems = workItems; this.permissions = permissions; this.attachments = attachments;
    }

    public ResponseEntity<byte[]> execute(UUID workItemId, UUID attachmentId) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        var attachment = attachments.getByIdAndWorkItem(attachmentId, workItemId);
        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename*=UTF-8''" + URLEncoder.encode(attachment.fileName, StandardCharsets.UTF_8))
            .contentType(MediaType.parseMediaType(attachment.contentType))
            .body(attachment.content);
    }
}
