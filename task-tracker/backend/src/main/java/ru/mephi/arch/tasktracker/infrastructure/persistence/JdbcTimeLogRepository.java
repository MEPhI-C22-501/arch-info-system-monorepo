package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.TimeLogRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.TimeLogEntry;

import java.sql.Date;
import java.util.List;
import java.util.UUID;

@Repository
public class JdbcTimeLogRepository implements TimeLogRepository {
    private final JdbcTemplate db;
    public JdbcTimeLogRepository(JdbcTemplate db) { this.db = db; }

    @Override public List<TimeLogEntry> findByWorkItem(UUID workItemId) {
        return db.query("SELECT * FROM time_log_entry WHERE work_item_id=? ORDER BY logged_date,created_at",
            (rs, i) -> new TimeLogEntry((UUID) rs.getObject("id"), (UUID) rs.getObject("work_item_id"),
                rs.getString("external_user_id"), rs.getDate("logged_date").toLocalDate(), rs.getBigDecimal("hours"),
                rs.getString("comment"), rs.getObject("created_at", java.time.OffsetDateTime.class)), workItemId);
    }

    @Override public void insert(TimeLogEntry entry) {
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,comment,created_at) VALUES(?,?,?,?,?,?,?)",
            entry.id, entry.workItemId, entry.externalUserId, Date.valueOf(entry.loggedDate), entry.hours, entry.comment, entry.createdAt);
    }

    @Override public java.math.BigDecimal sumHoursForWorkItem(UUID workItemId) {
        return db.queryForObject("SELECT COALESCE(SUM(hours),0) FROM time_log_entry WHERE work_item_id=?", java.math.BigDecimal.class, workItemId);
    }
}
