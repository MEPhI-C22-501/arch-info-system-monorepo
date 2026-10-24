package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.collaboration.Comment;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface CommentRepository {
    List<Comment> findByWorkItem(UUID workItemId);

    /** Throws ApiException.missing("commentId") if not found under that work item. */
    Comment getByIdAndWorkItem(UUID id, UUID workItemId);

    Optional<Comment> findByIdAndWorkItem(UUID id, UUID workItemId);

    void insert(Comment comment);

    void updateBody(UUID id, String body);

    void delete(UUID id);
}
