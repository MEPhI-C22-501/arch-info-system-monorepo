package ru.mephi.arch.tasktracker.infrastructure.persistence;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.math.BigDecimal;
import java.sql.Connection;
import java.time.OffsetDateTime;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Exercises the real SQL (recursive CTEs included) against a real Postgres via Testcontainers —
 * the dependency was already declared in pom.xml but unused until now. Schema setup applies
 * {@code 001-initial.sql} directly rather than booting the full Liquibase runner: it's the same
 * file the real changelog wraps, and this keeps the test fast and dependency-light.
 */
@Testcontainers
class JdbcWorkItemRepositoryTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:18-alpine");

    static JdbcTemplate db;
    JdbcWorkItemRepository repo;

    @BeforeAll
    static void migrate() throws Exception {
        var dataSource = new DriverManagerDataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        db = new JdbcTemplate(dataSource);
        try (Connection connection = dataSource.getConnection()) {
            ScriptUtils.executeSqlScript(connection, new ClassPathResource("db/changelog/001-initial.sql"));
            try(var statement=connection.createStatement()) {
                statement.execute(new ClassPathResource("db/changelog/002-review.sql").getContentAsString(java.nio.charset.StandardCharsets.UTF_8));
                statement.execute(new ClassPathResource("db/changelog/003-planning.sql").getContentAsString(java.nio.charset.StandardCharsets.UTF_8));
            }
        }
    }

    @BeforeEach
    void setUp() {
        repo = new JdbcWorkItemRepository(db);
        db.update("DELETE FROM audit_entry"); db.update("DELETE FROM notification");
        db.update("DELETE FROM work_item_iteration"); db.update("DELETE FROM time_log_entry");
        db.update("DELETE FROM comment"); db.update("DELETE FROM attachment");
        db.update("DELETE FROM work_item");
    }

    private WorkItem newTask(UUID id, UUID parentId) {
        return new WorkItem(id, WorkItemType.TASK, "Task " + id, "", statusId(), priorityId(), null,
            null, null, null, parentId, null, null, null, null, null, null, 0L, OffsetDateTime.now(), OffsetDateTime.now());
    }

    private UUID statusId() { return db.queryForObject("SELECT id FROM status LIMIT 1", UUID.class); }
    private UUID priorityId() { return db.queryForObject("SELECT id FROM priority LIMIT 1", UUID.class); }

    @Test void blockingLinksRejectCyclesAndSymmetricLinksRejectReverseDuplicates() {
        var permissions=org.mockito.Mockito.mock(ru.mephi.arch.tasktracker.application.port.PermissionPort.class);
        org.mockito.Mockito.when(permissions.currentSubject()).thenReturn("lead");
        var publisher=org.mockito.Mockito.mock(ru.mephi.arch.tasktracker.application.port.EventPublisherPort.class);
        var controller=new ru.mephi.arch.tasktracker.LinkController(db,repo,permissions,publisher);
        UUID a=UUID.randomUUID(),b=UUID.randomUUID(),c=UUID.randomUUID();
        repo.insert(newTask(a,null));repo.insert(newTask(b,null));repo.insert(newTask(c,null));
        controller.create(a,java.util.Map.of("targetId",b,"type","BLOCKS"));
        controller.create(b,java.util.Map.of("targetId",c,"type","BLOCKS"));
        assertThrows(ApiException.class,()->controller.create(c,java.util.Map.of("targetId",a,"type","BLOCKS")));
        controller.create(a,java.util.Map.of("targetId",c,"type","RELATED"));
        assertThrows(ApiException.class,()->controller.create(c,java.util.Map.of("targetId",a,"type","RELATED")));
    }

    @Test void insertThenGetByIdRoundTrips() {
        UUID id = UUID.randomUUID();
        repo.insert(newTask(id, null));
        var fetched = repo.getById(id);
        assertEquals("Task " + id, fetched.title);
        assertEquals(0L, fetched.version);
    }

    @Test void linksAreAuditedOnBothCardsAndRemovalSurvivesDeletingAnEndpoint() {
        var permissions = org.mockito.Mockito.mock(ru.mephi.arch.tasktracker.application.port.PermissionPort.class);
        org.mockito.Mockito.when(permissions.currentSubject()).thenReturn("lead");
        var audit = new JdbcAuditRepository(db);
        var listener = new ru.mephi.arch.tasktracker.infrastructure.event.AuditEventListener(audit);
        ru.mephi.arch.tasktracker.application.port.EventPublisherPort publisher = event -> {
            if (event instanceof ru.mephi.arch.tasktracker.domain.event.RecordableChange change) listener.on(change);
        };
        var links = new ru.mephi.arch.tasktracker.LinkController(db, repo, permissions, publisher);
        var delete = new ru.mephi.arch.tasktracker.application.workitem.DeleteWorkItem(repo, permissions, publisher);
        UUID first = UUID.randomUUID(), second = UUID.randomUUID();
        repo.insert(newTask(first, null));
        repo.insert(newTask(second, null));
        UUID link = (UUID) ((java.util.Map<?, ?>) links.create(first, java.util.Map.of("targetId", second, "type", "RELATED"))).get("id");
        links.delete(first, link);
        for (UUID id : java.util.List.of(first, second)) {
            var history = audit.findByWorkItem(id);
            assertEquals(2, history.size());
            assertEquals(link.toString(), ((java.util.Map<?, ?>) history.getFirst().get("newValues")).get("linkAdded"));
            assertEquals(link.toString(), ((java.util.Map<?, ?>) history.getLast().get("newValues")).get("linkRemoved"));
        }
        UUID remainingLink = (UUID) ((java.util.Map<?, ?>) links.create(first, java.util.Map.of("targetId", second, "type", "BLOCKS"))).get("id");
        delete.execute(second, second.toString());
        var last = (java.util.Map<?, ?>) audit.findByWorkItem(first).getLast().get("newValues");
        assertEquals(remainingLink.toString(), last.get("linkRemoved"));
        assertEquals("BLOCKS", last.get("linkType"));
        assertTrue(repo.findLinks(first).isEmpty());
    }

    @Test void getByIdThrowsOnMissingRow() {
        assertThrows(ApiException.class, () -> repo.getById(UUID.randomUUID()));
    }

    @Test void concurrentUpdatesDoNotSilentlyOverwriteEachOther() {
        UUID id = UUID.randomUUID();
        repo.insert(newTask(id, null));
        var first = repo.getById(id);
        var stale = repo.getById(id);
        first.applyFieldUpdate("First", "", first.statusId, first.priorityId, null, null, null, null, null, OffsetDateTime.now());
        stale.applyFieldUpdate("Second", "", stale.statusId, stale.priorityId, null, null, null, null, null, OffsetDateTime.now());
        repo.update(first);
        assertThrows(ApiException.class, () -> repo.update(stale));
        assertEquals("First", repo.getById(id).title);
    }

    @Test void decompositionPreservesTimeAlreadyRecordedOnTheParent() {
        UUID parent = UUID.randomUUID(), child = UUID.randomUUID();
        repo.insert(newTask(parent, null));
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,created_at) VALUES(?,?,'original-author',current_date,3,now())", UUID.randomUUID(), parent);
        var subtask = newTask(child, parent);
        subtask.plannedHours = new BigDecimal("5");
        repo.insert(subtask);
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,created_at) VALUES(?,?,'other-author',current_date,2,now())", UUID.randomUUID(), child);
        var summary = repo.computeHoursSummary(parent);
        assertEquals(0, new BigDecimal("5").compareTo(summary.actual()));
        assertEquals(0, new BigDecimal("5").compareTo(summary.planned()));
        assertEquals(2, repo.findDescendantIds(parent).size());
    }

    @Test void requiredSortsAndLargeOffsetsAreSupported() {
        UUID a = UUID.randomUUID(), b = UUID.randomUUID();
        repo.insert(newTask(a, null));
        repo.insert(newTask(b, null));
        db.update("UPDATE work_item SET type='BUG' WHERE id=?", b);
        for (String sort : java.util.List.of("type", "assignee", "iteration", "priority", "status")) {
            var filter = new ru.mephi.arch.tasktracker.application.port.WorkItemRepository.WorkItemFilter(
                null, null, null, null, null, null, sort, null, 1, 50);
            var page = repo.search(filter);
            assertEquals(2, page.items().size());
            if (sort.equals("type")) assertEquals(b, page.items().getFirst().id);
        }
        var distant = new ru.mephi.arch.tasktracker.application.port.WorkItemRepository.WorkItemFilter(
            null, null, null, null, null, null, "type", null, Integer.MAX_VALUE, 500);
        assertTrue(repo.search(distant).items().isEmpty());
    }

    @Test void updateBumpsWhateverVersionIsSet() {
        UUID id = UUID.randomUUID();
        repo.insert(newTask(id, null));
        var item = repo.getById(id);
        item.applyFieldUpdate("Renamed", "", item.statusId, item.priorityId, null, null, null, null, null, OffsetDateTime.now());
        repo.update(item);
        var fetched = repo.getById(id);
        assertEquals("Renamed", fetched.title);
        assertEquals(1L, fetched.version);
    }

    @Test void hasChildrenReflectsRealParentLinks() {
        UUID parent = UUID.randomUUID();
        repo.insert(newTask(parent, null));
        assertFalse(repo.hasChildren(parent));
        repo.insert(newTask(UUID.randomUUID(), parent));
        assertTrue(repo.hasChildren(parent));
    }

    @Test void isAncestorWalksTheRealParentChainViaRecursiveCte() {
        UUID grandparent = UUID.randomUUID(), parent = UUID.randomUUID(), child = UUID.randomUUID();
        repo.insert(newTask(grandparent, null));
        repo.insert(newTask(parent, grandparent));
        repo.insert(newTask(child, parent));
        assertTrue(repo.isAncestor(grandparent, child));
        assertTrue(repo.isAncestor(parent, child));
        assertFalse(repo.isAncestor(child, grandparent));
    }

    @Test void computeHoursSummaryAggregatesOverLeafDescendantsOnly() {
        UUID parent = UUID.randomUUID();
        repo.insert(newTask(parent, null));
        UUID leaf1 = UUID.randomUUID();
        UUID leaf2 = UUID.randomUUID();
        var l1 = newTask(leaf1, parent); l1.plannedHours = new BigDecimal("5.00");
        var l2 = newTask(leaf2, parent); l2.plannedHours = new BigDecimal("3.00");
        repo.insert(l1); repo.insert(l2);
        var summary = repo.computeHoursSummary(parent);
        assertEquals(new BigDecimal("8.00"), summary.planned());
        assertEquals(BigDecimal.ZERO, summary.actual());
    }

    @Test void deleteRemovesTheRow() {
        UUID id = UUID.randomUUID();
        repo.insert(newTask(id, null));
        repo.delete(id);
        assertTrue(repo.findById(id).isEmpty());
    }

    @Test void acquireExternalReferenceLockDoesNotThrowOutsideATransaction() {
        assertDoesNotThrow(() -> repo.acquireExternalReferenceLock("testing-service", "DEF-1"));
    }
}
