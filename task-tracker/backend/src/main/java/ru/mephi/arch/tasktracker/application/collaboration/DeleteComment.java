package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.application.port.CommentRepository;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.Comment;
import ru.mephi.arch.tasktracker.domain.event.CommentChanged;

import java.util.Map;
import java.util.UUID;

@Service
public class DeleteComment {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final CommentRepository comments;
    private final EventPublisherPort events;
    public DeleteComment(WorkItemRepository workItems, PermissionPort permissions, CommentRepository comments, EventPublisherPort events) {
        this.workItems = workItems; this.permissions = permissions; this.comments = comments; this.events = events;
    }

    @Transactional
    public void execute(UUID workItemId, UUID commentId) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        Comment original = comments.getByIdAndWorkItem(commentId, workItemId);
        if (!permissions.currentSubject().equals(original.authorExternalId)) permissions.require("comment.manage");
        comments.delete(commentId);
        workItems.touch(workItemId);
        events.publish(new CommentChanged(workItemId, permissions.currentSubject(), null,
            Map.of("commentRemoved", false), Map.of("commentRemoved", commentId.toString()), "Удалён комментарий"));
    }
}
