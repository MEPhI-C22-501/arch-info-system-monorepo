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

    @Test void insertThenGetByIdRoundTrips() {
        UUID id = UUID.randomUUID();
        repo.insert(newTask(id, null));
        var fetched = repo.getById(id);
        assertEquals("Task " + id, fetched.title);
        assertEquals(0L, fetched.version);
    }

    @Test void getByIdThrowsOnMissingRow() {
        assertThrows(ApiException.class, () -> repo.getById(UUID.randomUUID()));
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
