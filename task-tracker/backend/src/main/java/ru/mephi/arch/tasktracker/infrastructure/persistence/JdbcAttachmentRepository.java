package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.AttachmentRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.Attachment;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JdbcAttachmentRepository implements AttachmentRepository {
    private static final RowMapper<Attachment> METADATA_MAPPER = (rs, i) -> new Attachment(
        (UUID) rs.getObject("id"), (UUID) rs.getObject("work_item_id"), rs.getString("file_name"),
        rs.getLong("size_bytes"), rs.getString("content_type"), null,
        rs.getString("uploaded_by_external_id"), rs.getObject("uploaded_at", OffsetDateTime.class));
    private static final RowMapper<Attachment> FULL_MAPPER = (rs, i) -> new Attachment(
        (UUID) rs.getObject("id"), (UUID) rs.getObject("work_item_id"), rs.getString("file_name"),
        rs.getLong("size_bytes"), rs.getString("content_type"), rs.getBytes("content"),
        rs.getString("uploaded_by_external_id"), rs.getObject("uploaded_at", OffsetDateTime.class));

    private final JdbcTemplate db;
    public JdbcAttachmentRepository(JdbcTemplate db) { this.db = db; }

    @Override public List<Attachment> findMetadataByWorkItem(UUID workItemId) {
        return db.query("SELECT id,work_item_id,file_name,size_bytes,content_type,uploaded_by_external_id,uploaded_at " +
            "FROM attachment WHERE work_item_id=? ORDER BY uploaded_at", METADATA_MAPPER, workItemId);
    }

    @Override public Attachment getByIdAndWorkItem(UUID id, UUID workItemId) {
        return findByIdAndWorkItem(id, workItemId).orElseThrow(() -> ApiException.missing("attachmentId"));
    }

    @Override public Optional<Attachment> findByIdAndWorkItem(UUID id, UUID workItemId) {
        var rows = db.query("SELECT * FROM attachment WHERE id=? AND work_item_id=?", FULL_MAPPER, id, workItemId);
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.getFirst());
    }

    @Override public void insert(Attachment attachment) {
        db.update("INSERT INTO attachment(id,work_item_id,file_name,size_bytes,content_type,content,uploaded_by_external_id,uploaded_at) VALUES(?,?,?,?,?,?,?,?)",
            attachment.id, attachment.workItemId, attachment.fileName, attachment.sizeBytes, attachment.contentType,
            attachment.content, attachment.uploadedByExternalId, attachment.uploadedAt);
    }

    @Override public void delete(UUID id) { db.update("DELETE FROM attachment WHERE id=?", id); }
}
