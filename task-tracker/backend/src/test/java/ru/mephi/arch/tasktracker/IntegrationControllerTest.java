package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.core.io.ClassPathResource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.*;
import ru.mephi.arch.tasktracker.application.workitem.CreateWorkItem;
import ru.mephi.arch.tasktracker.application.workitem.ViewWorkItem;
import ru.mephi.arch.tasktracker.infrastructure.persistence.*;
import ru.mephi.arch.tasktracker.infrastructure.security.PermissionPortAdapter;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

/** Reports' live-ETL run against our own openapi.yaml (issue #159) found that
 * /api/v1/reports/* disagreed with our own contract, and that POST /bugs never
 * published a domain event at all. These tests pin down both fixes. */
@Testcontainers
class IntegrationControllerTest {
    @Container static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:18-alpine");
    static JdbcTemplate db;

    @BeforeAll static void migrate() throws Exception {
        var source = new DriverManagerDataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        db = new JdbcTemplate(source);
        try (var connection = source.getConnection(); var statement = connection.createStatement()) {
            for (String file : List.of("001-initial.sql", "002-review.sql"))
                statement.execute(new ClassPathResource("db/changelog/" + file).getContentAsString(StandardCharsets.UTF_8));
        }
    }

    @BeforeEach void clean() {
        db.update("DELETE FROM notification"); db.update("DELETE FROM audit_entry");
        db.update("DELETE FROM time_log_entry"); db.update("DELETE FROM work_item_iteration");
        db.update("DELETE FROM work_item"); db.update("DELETE FROM event_outbox");
    }
    @AfterEach void clearAuthentication() { SecurityContextHolder.clearContext(); }

    private void authAs(String subject, String... clientRoles) {
        var builder = Jwt.withTokenValue("test").header("alg", "none").subject(subject);
        if (clientRoles.length > 0) builder.claim("resource_access", Map.of("task-tracker", Map.of("roles", List.of(clientRoles))));
        SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(builder.build()));
    }

    private IntegrationController controller() {
        AccessService access = new AccessService(db, "");
        ChangeRecorder changes = new ChangeRecorder(db);
        WorkItemService items = new WorkItemService(db, access, changes);
        var workItems = new JdbcWorkItemRepository(db);
        var view = new ViewWorkItem(workItems);
        var outbox = new Outbox(db, "", "PLAINTEXT", "", "", "");
        CreateWorkItem create = new CreateWorkItem(workItems, new JdbcStatusRepository(db), new JdbcPriorityRepository(db),
            new JdbcTypeSettingRepository(db), new JdbcUserDirectoryRepository(db), new PermissionPortAdapter(access), outbox::record, view);
        return new IntegrationController(db, access, items, changes, create);
    }

    private UUID seedWorkItem(String title) {
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO work_item(id,type,title,description,status_id,priority_id,created_at,updated_at) VALUES(?,'TASK',?,'',"
            + "'00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000201',now(),now())", id, title);
        return id;
    }

    @Test void reportPagesIncludeTheirRealTotalNotJustTheSlicePage() {
        for (int i = 0; i < 3; i++) seedWorkItem("Item " + i);
        authAs("reports-account", "reports-service");
        @SuppressWarnings("unchecked") Map<String,Object> items = (Map<String,Object>) controller().reportItems(Map.of("pageSize", "2"));
        assertEquals(3L, ((Number) items.get("total")).longValue());
        assertEquals(2, ((List<?>) items.get("items")).size());

        UUID itemId = seedWorkItem("With time log");
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,created_at) VALUES(?,?,?,?,1,now())",
            UUID.randomUUID(), itemId, "member", java.sql.Date.valueOf("2026-11-04"));
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,created_at) VALUES(?,?,?,?,1,now())",
            UUID.randomUUID(), itemId, "member", java.sql.Date.valueOf("2026-11-05"));
        @SuppressWarnings("unchecked") Map<String,Object> logs = (Map<String,Object>) controller().reportTimeLogs(Map.of("pageSize", "1"));
        assertEquals(2L, ((Number) logs.get("total")).longValue());

        db.update("INSERT INTO audit_entry(id,work_item_id,actor_external_id,occurred_at,changed_fields,old_values,new_values) VALUES"
            + "(?,?,?,now(),'[]','{}','{}')", UUID.randomUUID(), itemId, "lead");
        db.update("INSERT INTO audit_entry(id,work_item_id,actor_external_id,occurred_at,changed_fields,old_values,new_values) VALUES"
            + "(?,?,?,now(),'[]','{}','{}')", UUID.randomUUID(), itemId, "lead");
        @SuppressWarnings("unchecked") Map<String,Object> history = (Map<String,Object>) controller().reportHistory(Map.of("pageSize", "1"));
        assertEquals(2L, ((Number) history.get("total")).longValue());
    }

    @Test void reportWorkItemsCarriesEveryFieldOpenapiRequires() {
        UUID parentId = seedWorkItem("Parent");
        UUID childId = UUID.randomUUID();
        db.update("INSERT INTO work_item(id,type,title,description,status_id,priority_id,parent_id,created_at,updated_at) VALUES(?,'SUBTASK',?,'',"
            + "'00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000201',?,now(),now())", childId, "Child", parentId);
        authAs("reports-account", "reports-service");
        @SuppressWarnings("unchecked") Map<String,Object> page = (Map<String,Object>) controller().reportItems(Map.of());
        @SuppressWarnings("unchecked") List<Map<String,Object>> rows = (List<Map<String,Object>>) page.get("items");
        var parentRow = rows.stream().filter(r -> parentId.equals(r.get("id"))).findFirst().orElseThrow();
        assertEquals("Parent", parentRow.get("title"));
        assertEquals("", parentRow.get("description"));
        assertNotNull(parentRow.get("statusId"));
        assertEquals(0L, ((Number) parentRow.get("version")).longValue());
        assertEquals(1, ((List<?>) parentRow.get("children")).size());
    }

    @Test void reportTimeLogsLoggedDateIsABareDateNotATimestamp() {
        UUID itemId = seedWorkItem("Has time");
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,created_at) VALUES(?,?,?,?,2.5,now())",
            UUID.randomUUID(), itemId, "member", java.sql.Date.valueOf("2026-11-04"));
        authAs("reports-account", "reports-service");
        @SuppressWarnings("unchecked") Map<String,Object> page = (Map<String,Object>) controller().reportTimeLogs(Map.of());
        @SuppressWarnings("unchecked") List<Map<String,Object>> rows = (List<Map<String,Object>>) page.get("items");
        assertEquals("2026-11-04", rows.getFirst().get("loggedDate"));
    }

    @Test void bugCreationPublishesAWorkItemCreatedEventAndDedupSkipsTheSecondCall() {
        authAs("service-account-testing-client", "testing-service");
        Map<String,Object> body = Map.of("externalSource", "qa-system", "externalDefectId", "DEF-1",
            "title", "Login broken", "description", "Cannot log in", "severity", "high",
            "environment", "staging", "testRunUrl", "https://qa/run/1");
        var response = controller().bug(body);
        assertEquals(201, response.getStatusCode().value());
        assertEquals(1, db.queryForObject("SELECT count(*) FROM event_outbox", Integer.class));
        UUID workItemId = (UUID) ((Map<?,?>) response.getBody()).get("id");
        var outboxRow = db.queryForMap("SELECT aggregate_id,payload FROM event_outbox");
        assertEquals(workItemId.toString(), outboxRow.get("aggregate_id"));
        assertTrue(outboxRow.get("payload").toString().contains("\"eventType\":\"WorkItemCreated\""));
        assertTrue(outboxRow.get("payload").toString().contains("\"externalSource\":\"qa-system\""));
        assertTrue(outboxRow.get("payload").toString().contains("\"externalDefectId\":\"DEF-1\""));

        var repeat = controller().bug(body);
        assertEquals(200, repeat.getStatusCode().value());
        assertEquals("already-exists", ((Map<?,?>) repeat.getBody()).get("status"));
        assertEquals(1, db.queryForObject("SELECT count(*) FROM event_outbox", Integer.class));
    }
}
