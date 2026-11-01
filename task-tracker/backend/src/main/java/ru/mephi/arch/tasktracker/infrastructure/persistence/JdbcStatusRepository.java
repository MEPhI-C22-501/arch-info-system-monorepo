package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.StatusRepository;

import java.util.UUID;

@Repository
public class JdbcStatusRepository implements StatusRepository {
    private final JdbcTemplate db;
    public JdbcStatusRepository(JdbcTemplate db) { this.db = db; }

    @Override public boolean isActive(UUID id) {
        Integer found = db.query("SELECT 1 FROM status WHERE id=? AND active=true", rs -> rs.next() ? 1 : null, id);
        return found != null;
    }

    @Override public UUID defaultStatusId() {
        return db.queryForObject("SELECT id FROM status WHERE active=true AND category='OPEN' ORDER BY board_order LIMIT 1", UUID.class);
    }

    @Override public StatusSummary findSummary(UUID id) {
        return db.queryForObject("SELECT name,category FROM status WHERE id=?",
            (rs, i) -> new StatusSummary(rs.getString("name"), rs.getString("category")), id);
    }
}
