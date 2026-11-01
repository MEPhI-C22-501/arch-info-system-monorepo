package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.TypeSettingRepository;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

@Repository
public class JdbcTypeSettingRepository implements TypeSettingRepository {
    private final JdbcTemplate db;
    public JdbcTypeSettingRepository(JdbcTemplate db) { this.db = db; }

    @Override public boolean isEnabled(WorkItemType type) {
        return db.queryForObject("SELECT count(*) FROM type_setting WHERE type=? AND enabled=true", Integer.class, type.name()) > 0;
    }
}
