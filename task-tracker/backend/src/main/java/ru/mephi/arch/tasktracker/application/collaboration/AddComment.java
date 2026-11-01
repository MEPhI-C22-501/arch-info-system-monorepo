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

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

@Service
public class AddComment {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final CommentRepository comments;
    private final EventPublisherPort events;
    public AddComment(WorkItemRepository workItems, PermissionPort permissions, CommentRepository comments, EventPublisherPort events) {
        this.workItems = workItems; this.permissions = permissions; this.comments = comments; this.events = events;
    }

    @Transactional
    public Map<String, Object> execute(UUID workItemId, Map<String, Object> body) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        permissions.require("comment.create");
        String text = Values.str(body, "body", true);
        UUID id = UUID.randomUUID();
        String actor = permissions.currentSubject();
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        comments.insert(new Comment(id, workItemId, actor, text, now));
        workItems.touch(workItemId);
        events.publish(new CommentChanged(workItemId, actor, null, Map.of("commentAdded", false),
            Map.of("commentAdded", id.toString()), "Добавлен комментарий"));
        return Map.of("id", id, "body", text, "authorId", actor, "createdAt", now);
    }
}
