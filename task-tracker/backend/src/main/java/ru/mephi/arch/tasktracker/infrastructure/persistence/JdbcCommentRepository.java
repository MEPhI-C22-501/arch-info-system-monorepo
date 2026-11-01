package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.CommentRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.Comment;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JdbcCommentRepository implements CommentRepository {
    private static final RowMapper<Comment> ROW_MAPPER = (rs, i) -> new Comment(
        (UUID) rs.getObject("id"), (UUID) rs.getObject("work_item_id"), rs.getString("author_external_id"),
        rs.getString("body"), rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcTemplate db;
    public JdbcCommentRepository(JdbcTemplate db) { this.db = db; }

    @Override public List<Comment> findByWorkItem(UUID workItemId) {
        return db.query("SELECT * FROM comment WHERE work_item_id=? ORDER BY created_at,id", ROW_MAPPER, workItemId);
    }

    @Override public Comment getByIdAndWorkItem(UUID id, UUID workItemId) {
        return findByIdAndWorkItem(id, workItemId).orElseThrow(() -> ApiException.missing("commentId"));
    }

    @Override public Optional<Comment> findByIdAndWorkItem(UUID id, UUID workItemId) {
        var rows = db.query("SELECT * FROM comment WHERE id=? AND work_item_id=?", ROW_MAPPER, id, workItemId);
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.getFirst());
    }

    @Override public void insert(Comment comment) {
        db.update("INSERT INTO comment(id,work_item_id,author_external_id,body,created_at) VALUES(?,?,?,?,?)",
            comment.id, comment.workItemId, comment.authorExternalId, comment.body, comment.createdAt);
    }

    @Override public void updateBody(UUID id, String body) { db.update("UPDATE comment SET body=? WHERE id=?", body, id); }

    @Override public void delete(UUID id) { db.update("DELETE FROM comment WHERE id=?", id); }
}
