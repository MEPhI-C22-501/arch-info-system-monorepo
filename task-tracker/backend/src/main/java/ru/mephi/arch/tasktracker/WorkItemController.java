package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import ru.mephi.arch.tasktracker.application.collaboration.*;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.application.workitem.*;

import java.net.URI;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/work-items")
public class WorkItemController {
    private final ListWorkItems listWorkItems;
    private final CreateWorkItem createWorkItem;
    private final GetWorkItem getWorkItem;
    private final UpdateWorkItem updateWorkItem;
    private final DeleteWorkItem deleteWorkItem;
    private final GetWorkItemHistory getWorkItemHistory;
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final ListComments listComments;
    private final AddComment addComment;
    private final EditComment editComment;
    private final DeleteComment deleteComment;
    private final ListTimeLogs listTimeLogs;
    private final LogTime logTime;
    private final ListAttachments listAttachments;
    private final UploadAttachment uploadAttachment;
    private final DownloadAttachment downloadAttachment;
    private final DeleteAttachment deleteAttachment;

    public WorkItemController(ListWorkItems listWorkItems, CreateWorkItem createWorkItem, GetWorkItem getWorkItem,
                               UpdateWorkItem updateWorkItem, DeleteWorkItem deleteWorkItem,
                               GetWorkItemHistory getWorkItemHistory, WorkItemRepository workItems,
                               PermissionPort permissions, ListComments listComments, AddComment addComment,
                               EditComment editComment, DeleteComment deleteComment, ListTimeLogs listTimeLogs,
                               LogTime logTime, ListAttachments listAttachments, UploadAttachment uploadAttachment,
                               DownloadAttachment downloadAttachment, DeleteAttachment deleteAttachment) {
        this.listWorkItems = listWorkItems; this.createWorkItem = createWorkItem; this.getWorkItem = getWorkItem;
        this.updateWorkItem = updateWorkItem; this.deleteWorkItem = deleteWorkItem;
        this.getWorkItemHistory = getWorkItemHistory; this.workItems = workItems; this.permissions = permissions;
        this.listComments = listComments; this.addComment = addComment; this.editComment = editComment;
        this.deleteComment = deleteComment; this.listTimeLogs = listTimeLogs; this.logTime = logTime;
        this.listAttachments = listAttachments; this.uploadAttachment = uploadAttachment;
        this.downloadAttachment = downloadAttachment; this.deleteAttachment = deleteAttachment;
    }

    @GetMapping public Map<String, Object> list(@RequestParam Map<String, String> filters) { return listWorkItems.execute(filters); }

    @PostMapping public ResponseEntity<?> create(@RequestBody Map<String, Object> body) {
        permissions.require("item.create");
        var item = createWorkItem.execute(body, permissions.currentSubject(), null);
        return ResponseEntity.created(URI.create("/api/v1/work-items/" + item.get("id"))).body(item);
    }

    @GetMapping("/{id}") public Map<String, Object> one(@PathVariable UUID id) { return getWorkItem.execute(id); }

    @PatchMapping("/{id}") public Map<String, Object> update(@PathVariable UUID id, @RequestBody Map<String, Object> body) {
        // read-before-write ownership check, mirroring the old WorkItemService.update() wrapper —
        // UpdateWorkItem.execute itself stays permission-check-free for item.update/ownership so
        // Excel import can keep reusing it without that gate.
        permissions.requireItemWritable(workItems.getById(id).assigneeId);
        return updateWorkItem.execute(id, body, permissions.currentSubject(), null);
    }

    @DeleteMapping("/{id}") public ResponseEntity<?> delete(@PathVariable UUID id,
            @RequestHeader(value = "X-Confirm-Hard-Delete", required = false) String confirmation) {
        deleteWorkItem.execute(id, confirmation);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/{id}/history") public Object history(@PathVariable UUID id) { return getWorkItemHistory.execute(id); }

    @GetMapping("/{id}/comments") public Object comments(@PathVariable UUID id) { return listComments.execute(id); }
    @PostMapping("/{id}/comments") public ResponseEntity<?> comment(@PathVariable UUID id, @RequestBody Map<String, Object> body) { return ResponseEntity.status(201).body(addComment.execute(id, body)); }
    @PatchMapping("/{id}/comments/{commentId}") public Object editComment(@PathVariable UUID id, @PathVariable UUID commentId, @RequestBody Map<String, Object> body) { return editComment.execute(id, commentId, body); }
    @DeleteMapping("/{id}/comments/{commentId}") public ResponseEntity<?> deleteComment(@PathVariable UUID id, @PathVariable UUID commentId) { deleteComment.execute(id, commentId); return ResponseEntity.noContent().build(); }
    @GetMapping("/{id}/time-logs") public Object timeLogs(@PathVariable UUID id) { return listTimeLogs.execute(id); }
    @PostMapping("/{id}/time-logs") public ResponseEntity<?> timeLog(@PathVariable UUID id, @RequestBody Map<String, Object> body) { return ResponseEntity.status(201).body(logTime.execute(id, body)); }
    @GetMapping("/{id}/attachments") public Object attachments(@PathVariable UUID id) { return listAttachments.execute(id); }
    @PostMapping("/{id}/attachments") public ResponseEntity<?> attach(@PathVariable UUID id, @RequestParam("file") org.springframework.web.multipart.MultipartFile file) throws java.io.IOException { return ResponseEntity.status(201).body(uploadAttachment.execute(id, file)); }
    @GetMapping("/{id}/attachments/{attachmentId}") public ResponseEntity<byte[]> download(@PathVariable UUID id, @PathVariable UUID attachmentId) { return downloadAttachment.execute(id, attachmentId); }
    @DeleteMapping("/{id}/attachments/{attachmentId}") public ResponseEntity<?> deleteAttachment(@PathVariable UUID id, @PathVariable UUID attachmentId) { deleteAttachment.execute(id, attachmentId); return ResponseEntity.noContent().build(); }
}
