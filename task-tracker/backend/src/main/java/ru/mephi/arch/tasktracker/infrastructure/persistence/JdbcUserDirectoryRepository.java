package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.UserDirectoryRepository;

@Repository
public class JdbcUserDirectoryRepository implements UserDirectoryRepository {
    public static final String ACTIVE_SUBJECT = """
        SELECT 1 FROM user_cache WHERE external_user_id=? AND active=true
        AND EXISTS (SELECT 1 FROM directory_meta WHERE singleton=true AND last_success_at >= now() - interval '1 hour')
        """;

    private final JdbcTemplate db;
    public JdbcUserDirectoryRepository(JdbcTemplate db) { this.db = db; }

    @Override public boolean isActive(String externalUserId) {
        Integer found = db.query(ACTIVE_SUBJECT,
            rs -> rs.next() ? 1 : null, externalUserId);
        return found != null;
    }
}
