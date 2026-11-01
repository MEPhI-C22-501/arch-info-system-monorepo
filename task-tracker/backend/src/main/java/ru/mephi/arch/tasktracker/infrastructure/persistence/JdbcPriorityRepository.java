package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.PriorityRepository;

import java.util.UUID;

@Repository
public class JdbcPriorityRepository implements PriorityRepository {
    private final JdbcTemplate db;
    public JdbcPriorityRepository(JdbcTemplate db) { this.db = db; }

    @Override public boolean isActive(UUID id) {
        Integer found = db.query("SELECT 1 FROM priority WHERE id=? AND active=true", rs -> rs.next() ? 1 : null, id);
        return found != null;
    }

    @Override public UUID defaultPriorityId() {
        return db.queryForObject("SELECT id FROM priority WHERE active=true ORDER BY sort_order LIMIT 1", UUID.class);
    }
}
