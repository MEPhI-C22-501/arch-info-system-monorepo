package ru.mephi.arch.tasktracker.infrastructure.persistence;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.application.port.AuditRepository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Repository
public class JdbcAuditRepository implements AuditRepository {
    private final JdbcTemplate db;
    private final ObjectMapper json = new ObjectMapper().findAndRegisterModules();
    public JdbcAuditRepository(JdbcTemplate db) { this.db = db; }

    @Override public void record(UUID workItemId, String actorId, String source, OffsetDateTime occurredAt,
                                  List<String> changedFields, Map<String, Object> oldValues, Map<String, Object> newValues) {
        db.update("INSERT INTO audit_entry(id,work_item_id,actor_external_id,external_source,occurred_at,changed_fields,old_values,new_values) " +
                "VALUES (?,?,?,?,?,CAST(? AS jsonb),CAST(? AS jsonb),CAST(? AS jsonb))",
            UUID.randomUUID(), workItemId, source == null ? actorId : null, source, occurredAt,
            toJson(changedFields), toJson(oldValues), toJson(newValues));
    }

    @Override public List<Map<String, Object>> findByWorkItem(UUID workItemId) {
        return db.queryForList("SELECT id,actor_external_id AS \"actorId\",external_source AS \"externalSource\"," +
            "occurred_at AS \"occurredAt\",changed_fields AS \"changedFields\",old_values AS \"oldValues\"," +
            "new_values AS \"newValues\" FROM audit_entry WHERE work_item_id=? ORDER BY occurred_at,id", workItemId);
    }

    private String toJson(Object value) {
        try { return json.writeValueAsString(value); }
        catch (JsonProcessingException e) { throw new IllegalStateException(e); }
    }
}
