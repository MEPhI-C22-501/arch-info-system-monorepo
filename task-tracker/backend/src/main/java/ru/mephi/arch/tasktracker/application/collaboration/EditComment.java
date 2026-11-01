package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.CommentRepository;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.Comment;
import ru.mephi.arch.tasktracker.domain.event.CommentChanged;

import java.util.Map;
import java.util.UUID;

@Service
public class EditComment {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final CommentRepository comments;
    private final EventPublisherPort events;
    public EditComment(WorkItemRepository workItems, PermissionPort permissions, CommentRepository comments, EventPublisherPort events) {
        this.workItems = workItems; this.permissions = permissions; this.comments = comments; this.events = events;
    }

    @Transactional
    public Map<String, Object> execute(UUID workItemId, UUID commentId, Map<String, Object> body) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        Comment original = comments.getByIdAndWorkItem(commentId, workItemId);
        canManage(original);
        String text = Values.str(body, "body", true);
        if (!text.equals(original.body)) {
            comments.updateBody(commentId, text);
            workItems.touch(workItemId);
            events.publish(new CommentChanged(workItemId, permissions.currentSubject(), null,
                Map.of("comment", original.body), Map.of("comment", text), "Изменён комментарий"));
        }
        return Map.of("id", commentId, "body", text, "authorId", original.authorExternalId, "createdAt", original.createdAt);
    }

    private void canManage(Comment comment) {
        if (!permissions.currentSubject().equals(comment.authorExternalId)) permissions.require("comment.manage");
    }
}
