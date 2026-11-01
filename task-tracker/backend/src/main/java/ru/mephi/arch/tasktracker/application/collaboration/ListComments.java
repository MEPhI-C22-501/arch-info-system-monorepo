package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.CommentRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ListComments {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final CommentRepository comments;
    public ListComments(WorkItemRepository workItems, PermissionPort permissions, CommentRepository comments) {
        this.workItems = workItems; this.permissions = permissions; this.comments = comments;
    }

    /** Returns view-model maps (not the domain entity) so the wire shape — {@code authorId}, not
     * {@code authorExternalId} — stays exactly what the frontend/openapi.yaml already expect. */
    public List<Map<String, Object>> execute(UUID workItemId) {
        permissions.requireItemReadableOrQa(workItems.getById(workItemId).assigneeId);
        return comments.findByWorkItem(workItemId).stream()
            .<Map<String, Object>>map(c -> Map.of("id", c.id, "body", c.body, "authorId", c.authorExternalId, "createdAt", c.createdAt))
            .toList();
    }
}
