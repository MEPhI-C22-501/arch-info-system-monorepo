package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.HoursSummary;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.math.BigDecimal;
import java.sql.Date;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JdbcWorkItemRepository implements WorkItemRepository {
    private static final RowMapper<WorkItem> ROW_MAPPER = (rs, i) -> new WorkItem(
        (UUID) rs.getObject("id"), WorkItemType.valueOf(rs.getString("type")), rs.getString("title"),
        rs.getString("description"), (UUID) rs.getObject("status_id"), (UUID) rs.getObject("priority_id"),
        rs.getString("assignee_external_id"),
        rs.getDate("start_date") == null ? null : rs.getDate("start_date").toLocalDate(),
        rs.getDate("due_date") == null ? null : rs.getDate("due_date").toLocalDate(),
        rs.getBigDecimal("planned_hours"), (UUID) rs.getObject("parent_id"),
        rs.getString("external_source"), rs.getString("external_defect_id"), rs.getString("severity"),
        rs.getString("environment"), rs.getString("test_run_url"), rs.getString("test_case_url"),
        rs.getLong("version"), rs.getObject("created_at", OffsetDateTime.class),
        rs.getObject("updated_at", OffsetDateTime.class));

    private final JdbcTemplate db;
    public JdbcWorkItemRepository(JdbcTemplate db) { this.db = db; }

    @Override public WorkItem getById(UUID id) {
        return findById(id).orElseThrow(() -> ApiException.missing("workItemId"));
    }

    @Override public Optional<WorkItem> findById(UUID id) {
        var rows = db.query("SELECT * FROM work_item WHERE id=?", ROW_MAPPER, id);
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.getFirst());
    }

    @Override public void insert(WorkItem item) {
        db.update("INSERT INTO work_item(id,type,title,description,status_id,priority_id,assignee_external_id," +
                "start_date,due_date,planned_hours,parent_id,external_source,external_defect_id,severity," +
                "environment,test_run_url,test_case_url,version,created_at,updated_at) " +
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            item.id, item.type.name(), item.title, item.description, item.statusId, item.priorityId, item.assigneeId,
            sqlDate(item.startDate), sqlDate(item.dueDate), item.plannedHours, item.parentId, item.externalSource,
            item.externalDefectId, item.severity, item.environment, item.testRunUrl, item.testCaseUrl,
            item.version, item.createdAt, item.updatedAt);
    }

    @Override public void update(WorkItem item) {
        db.update("UPDATE work_item SET title=?,description=?,status_id=?,priority_id=?,assignee_external_id=?," +
                "start_date=?,due_date=?,planned_hours=?,parent_id=?,version=?,updated_at=? WHERE id=?",
            item.title, item.description, item.statusId, item.priorityId, item.assigneeId,
            sqlDate(item.startDate), sqlDate(item.dueDate), item.plannedHours, item.parentId,
            item.version, item.updatedAt, item.id);
    }

    @Override public void delete(UUID id) { db.update("DELETE FROM work_item WHERE id=?", id); }

    @Override public boolean hasChildren(UUID id) {
        return db.queryForObject("SELECT count(*) FROM work_item WHERE parent_id=?", Integer.class, id) > 0;
    }

    @Override public List<WorkItem.ChildSummary> findChildren(UUID id) {
        return db.query("SELECT id,type,title,status_id FROM work_item WHERE parent_id=? ORDER BY created_at",
            (rs, i) -> new WorkItem.ChildSummary((UUID) rs.getObject("id"), WorkItemType.valueOf(rs.getString("type")),
                rs.getString("title"), (UUID) rs.getObject("status_id")), id);
    }

    @Override public HoursSummary computeHoursSummary(UUID id) {
        var totals = db.queryForMap("WITH RECURSIVE d AS (SELECT id,planned_hours FROM work_item WHERE id=? " +
            "UNION ALL SELECT w.id,w.planned_hours FROM work_item w JOIN d ON w.parent_id=d.id), " +
            "leaves AS (SELECT d.id,d.planned_hours FROM d WHERE NOT EXISTS(SELECT 1 FROM work_item c WHERE c.parent_id=d.id)) " +
            "SELECT COALESCE(SUM(planned_hours),0) AS planned, " +
            "(SELECT COALESCE(SUM(t.hours),0) FROM time_log_entry t JOIN leaves l ON l.id=t.work_item_id) AS actual, " +
            "COUNT(*) FILTER (WHERE planned_hours IS NULL) AS unestimated FROM leaves", id);
        return new HoursSummary((BigDecimal) totals.get("planned"), (BigDecimal) totals.get("actual"),
            ((Number) totals.get("unestimated")).longValue());
    }

    @Override public Optional<UUID> findCurrentUnfinishedIterationId(UUID id) {
        var rows = db.queryForList("SELECT wi.iteration_id FROM work_item_iteration wi JOIN iteration i ON i.id=wi.iteration_id " +
            "WHERE wi.work_item_id=? AND wi.removed_at IS NULL AND i.state<>'COMPLETED' LIMIT 1", id);
        return rows.isEmpty() ? Optional.empty() : Optional.of((UUID) rows.getFirst().get("iteration_id"));
    }

    @Override public boolean isAncestor(UUID candidateAncestorId, UUID startFromId) {
        Boolean found = db.queryForObject(
            "WITH RECURSIVE chain AS (SELECT id,parent_id FROM work_item WHERE id=? " +
                "UNION ALL SELECT w.id,w.parent_id FROM work_item w JOIN chain c ON w.id=c.parent_id) " +
                "SELECT EXISTS(SELECT 1 FROM chain WHERE id=?)", Boolean.class, startFromId, candidateAncestorId);
        return Boolean.TRUE.equals(found);
    }

    @Override public List<UUID> findLeafDescendantIds(UUID rootId) {
        return db.queryForList(
            "WITH RECURSIVE d AS (SELECT id FROM work_item WHERE id=? " +
                "UNION ALL SELECT w.id FROM work_item w JOIN d ON w.parent_id=d.id) " +
                "SELECT d.id FROM d WHERE NOT EXISTS(SELECT 1 FROM work_item c WHERE c.parent_id=d.id)", UUID.class, rootId);
    }

    @Override public Optional<UUID> findNearestProjectAncestor(UUID id) {
        var rows = db.queryForList(
            "WITH RECURSIVE chain AS (SELECT id,type,parent_id FROM work_item WHERE id=? " +
                "UNION ALL SELECT w.id,w.type,w.parent_id FROM work_item w JOIN chain c ON w.id=c.parent_id) " +
                "SELECT id FROM chain WHERE type='PROJECT' LIMIT 1", UUID.class, id);
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.getFirst());
    }

    @Override public WorkItemPage search(WorkItemFilter filter) {
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new ArrayList<>();
        if (filter.type() != null && !filter.type().isBlank()) { where.append(" AND w.type=?"); args.add(filter.type()); }
        if (filter.statusId() != null) { where.append(" AND w.status_id=?"); args.add(filter.statusId()); }
        if (filter.priorityId() != null) { where.append(" AND w.priority_id=?"); args.add(filter.priorityId()); }
        if (filter.assigneeId() != null && !filter.assigneeId().isBlank()) { where.append(" AND w.assignee_external_id=?"); args.add(filter.assigneeId()); }
        if (filter.iterationId() != null) {
            where.append(" AND EXISTS (SELECT 1 FROM work_item_iteration wi WHERE wi.work_item_id=w.id AND wi.iteration_id=? AND wi.removed_at IS NULL)");
            args.add(filter.iterationId());
        }
        if (filter.restrictToAssigneeId() != null) { where.append(" AND w.assignee_external_id=?"); args.add(filter.restrictToAssigneeId()); }
        if (filter.search() != null && !filter.search().isBlank()) { where.append(" AND lower(w.title) LIKE ?"); args.add("%" + filter.search().toLowerCase() + "%"); }
        String base = " FROM work_item w JOIN status s ON s.id=w.status_id JOIN priority p ON p.id=w.priority_id" + where;
        long total = db.queryForObject("SELECT count(*)" + base, Long.class, args.toArray());
        String sort = switch (Objects.toString(filter.sort(), "dueDate")) {
            case "priority" -> "p.sort_order,w.created_at";
            case "status" -> "s.board_order,w.created_at";
            case "createdAt" -> "w.created_at DESC";
            default -> "w.due_date NULLS LAST,w.created_at";
        };
        var queryArgs = new ArrayList<>(args);
        queryArgs.add(filter.size());
        queryArgs.add((filter.page() - 1) * filter.size());
        var ids = db.queryForList("SELECT w.id" + base + " ORDER BY " + sort + " LIMIT ? OFFSET ?", UUID.class, queryArgs.toArray());
        List<WorkItem> items = ids.stream().map(this::getById).toList();
        return new WorkItemPage(items, filter.page(), filter.size(), total);
    }

    @Override public Optional<WorkItem> findByExternalReference(String source, String externalId) {
        var rows = db.query("SELECT * FROM work_item WHERE external_source=? AND external_defect_id=?", ROW_MAPPER, source, externalId);
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.getFirst());
    }

    @Override public void acquireExternalReferenceLock(String source, String externalId) {
        db.queryForObject("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", Object.class, source + ":" + externalId);
    }

    @Override public void touch(UUID id) {
        db.update("UPDATE work_item SET version=version+1,updated_at=? WHERE id=?", OffsetDateTime.now(java.time.ZoneOffset.UTC), id);
    }

    @Override public void lockForUpdate(UUID id) { db.queryForMap("SELECT id FROM work_item WHERE id=? FOR UPDATE", id); }

    private static Date sqlDate(java.time.LocalDate date) { return date == null ? null : Date.valueOf(date); }
}
