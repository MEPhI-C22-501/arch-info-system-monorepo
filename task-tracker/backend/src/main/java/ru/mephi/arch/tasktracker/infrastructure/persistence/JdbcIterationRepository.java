package ru.mephi.arch.tasktracker.infrastructure.persistence;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.domain.iteration.CapacityEntry;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;
import ru.mephi.arch.tasktracker.domain.iteration.IterationState;

import java.math.BigDecimal;
import java.sql.Date;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JdbcIterationRepository implements IterationRepository {
    private static final RowMapper<Iteration> ROW_MAPPER = (rs, i) -> new Iteration(
        (UUID) rs.getObject("id"), rs.getString("name"), rs.getString("description"),
        rs.getDate("start_date").toLocalDate(), rs.getDate("end_date").toLocalDate(),
        IterationState.valueOf(rs.getString("state")), rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcTemplate db;
    private final ObjectMapper json = new ObjectMapper().findAndRegisterModules();
    public JdbcIterationRepository(JdbcTemplate db) { this.db = db; }

    @Override public Iteration getById(UUID id) {
        var rows = db.query("SELECT * FROM iteration WHERE id=?", ROW_MAPPER, id);
        if (rows.isEmpty()) throw ApiException.missing("iterationId");
        return rows.getFirst();
    }

    @Override public List<Iteration> findAll() {
        return db.query("SELECT * FROM iteration ORDER BY start_date DESC", ROW_MAPPER);
    }

    @Override public void insert(Iteration iteration) {
        db.update("INSERT INTO iteration(id,name,description,start_date,end_date,state,created_at) VALUES(?,?,?,?,?,?,?)",
            iteration.id, iteration.name, iteration.description, Date.valueOf(iteration.startDate),
            Date.valueOf(iteration.endDate), iteration.state.name(), iteration.createdAt);
    }

    @Override public void update(Iteration iteration) {
        db.update("UPDATE iteration SET name=?,description=?,start_date=?,end_date=? WHERE id=?",
            iteration.name, iteration.description, Date.valueOf(iteration.startDate), Date.valueOf(iteration.endDate), iteration.id);
    }

    @Override public void activate(UUID id, Map<String, Object> baselineSnapshot) {
        db.update("UPDATE iteration SET state='ACTIVE',baseline_snapshot=CAST(? AS jsonb) WHERE id=?", toJson(baselineSnapshot), id);
    }

    @Override public void complete(UUID id, Map<String, Object> resultSnapshot) {
        db.update("UPDATE iteration SET state='COMPLETED',result_snapshot=CAST(? AS jsonb) WHERE id=?", toJson(resultSnapshot), id);
    }

    @Override public Optional<Map<String, Object>> findBaselineSnapshot(UUID id) {
        String raw = db.queryForObject("SELECT baseline_snapshot FROM iteration WHERE id=?", String.class, id);
        return raw == null ? Optional.empty() : Optional.of(fromJson(raw));
    }

    @Override public Optional<Map<String, Object>> findResultSnapshot(UUID id) {
        String raw = db.queryForObject("SELECT result_snapshot FROM iteration WHERE id=?", String.class, id);
        return raw == null ? Optional.empty() : Optional.of(fromJson(raw));
    }

    @Override public List<UUID> findActiveMemberIds(UUID iterationId) {
        return db.queryForList("SELECT work_item_id FROM work_item_iteration WHERE iteration_id=? AND removed_at IS NULL ORDER BY added_at",
            UUID.class, iterationId);
    }

    @Override public boolean isMember(UUID iterationId, UUID workItemId) {
        return db.queryForObject("SELECT count(*) FROM work_item_iteration WHERE iteration_id=? AND work_item_id=? AND removed_at IS NULL",
            Integer.class, iterationId, workItemId) > 0;
    }

    @Override public boolean hasOtherUnfinishedMembership(UUID workItemId, UUID excludingIterationId) {
        return db.queryForObject(
            "SELECT count(*) FROM work_item_iteration wi JOIN iteration i ON i.id=wi.iteration_id " +
                "WHERE wi.work_item_id=? AND wi.removed_at IS NULL AND i.state<>'COMPLETED' AND i.id<>?",
            Integer.class, workItemId, excludingIterationId) > 0;
    }

    @Override public void addMember(UUID iterationId, UUID workItemId) {
        db.update("INSERT INTO work_item_iteration(id,iteration_id,work_item_id,added_at) VALUES(?,?,?,?)",
            UUID.randomUUID(), iterationId, workItemId, OffsetDateTime.now(java.time.ZoneOffset.UTC));
    }

    @Override public boolean removeMember(UUID iterationId, UUID workItemId) {
        int changed = db.update("UPDATE work_item_iteration SET removed_at=? WHERE iteration_id=? AND work_item_id=? AND removed_at IS NULL",
            OffsetDateTime.now(java.time.ZoneOffset.UTC), iterationId, workItemId);
        return changed > 0;
    }

    @Override public void upsertCapacity(UUID iterationId, String externalUserId, BigDecimal availableHours) {
        db.update("INSERT INTO capacity_entry(iteration_id,external_user_id,available_hours) VALUES(?,?,?) " +
            "ON CONFLICT(iteration_id,external_user_id) DO UPDATE SET available_hours=EXCLUDED.available_hours",
            iterationId, externalUserId, availableHours);
    }

    @Override public List<CapacityEntry> findCapacity(UUID iterationId) {
        return db.query("SELECT external_user_id,available_hours FROM capacity_entry WHERE iteration_id=? ORDER BY external_user_id",
            (rs, i) -> new CapacityEntry(rs.getString("external_user_id"), rs.getBigDecimal("available_hours")), iterationId);
    }

    private String toJson(Object value) {
        try { return json.writeValueAsString(value); }
        catch (JsonProcessingException e) { throw new IllegalStateException(e); }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> fromJson(String value) {
        try { return json.readValue(value, Map.class); }
        catch (JsonProcessingException e) { throw new IllegalStateException(e); }
    }
}
