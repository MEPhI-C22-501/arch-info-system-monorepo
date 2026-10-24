package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.NotificationRepository;

import java.time.OffsetDateTime;
import java.util.UUID;

@Repository
public class JdbcNotificationRepository implements NotificationRepository {
    private final JdbcTemplate db;
    public JdbcNotificationRepository(JdbcTemplate db) { this.db = db; }

    @Override public void create(String recipientId, UUID workItemId, String workItemPublicId, String title,
                                  String message, String actor, OffsetDateTime createdAt) {
        db.update("INSERT INTO notification(id,recipient_external_id,work_item_id,work_item_public_id,work_item_title,message,actor,created_at) " +
                "VALUES (?,?,?,?,?,?,?,?)",
            UUID.randomUUID(), recipientId, workItemId, workItemPublicId, title, message, actor, createdAt);
    }
}
