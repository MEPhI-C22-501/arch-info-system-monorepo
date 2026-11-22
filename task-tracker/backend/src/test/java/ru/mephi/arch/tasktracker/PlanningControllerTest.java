package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.core.io.ClassPathResource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.*;
import ru.mephi.arch.tasktracker.application.workitem.*;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.infrastructure.persistence.*;
import ru.mephi.arch.tasktracker.domain.event.RecordableChange;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@Testcontainers
class PlanningControllerTest {
    @Container static final PostgreSQLContainer<?> POSTGRES=new PostgreSQLContainer<>("postgres:18-alpine");
    static JdbcTemplate db;
    static TransactionTemplate tx;
    PlanningController controller;
    AccessService access;
    WorkItemService items;
    @BeforeAll static void schema() throws Exception {
        var source=new DriverManagerDataSource(POSTGRES.getJdbcUrl(),POSTGRES.getUsername(),POSTGRES.getPassword());
        db=new JdbcTemplate(source);tx=new TransactionTemplate(new DataSourceTransactionManager(source));
        try(var connection=source.getConnection();var statement=connection.createStatement()) {
            for(String file:List.of("001-initial.sql","002-review.sql","003-planning.sql")) statement.execute(new ClassPathResource("db/changelog/"+file).getContentAsString(StandardCharsets.UTF_8));
        }
    }
    @BeforeEach void setup() {
        db.execute("TRUNCATE planning_binding,planning_publication,work_item CASCADE");
        access=mock(AccessService.class);when(access.subject()).thenReturn("planning-account");
        when(access.clientRole("planning-service")).thenReturn(true);
        var changes=new ChangeRecorder(db);items=new WorkItemService(db,access,changes);
        var repo=new JdbcWorkItemRepository(db);var view=new ViewWorkItem(repo);
        var permissions=mock(PermissionPort.class);
        var outbox=new Outbox(db,"","PLAINTEXT","","","");
        EventPublisherPort events=event->{
            if(event instanceof RecordableChange change) changes.record(change.workItemId(),change.actorId(),change.source(),change.oldValues(),change.newValues(),change.message());
            outbox.record(event);
        };
        var create=new CreateWorkItem(repo,new JdbcStatusRepository(db),new JdbcPriorityRepository(db),new JdbcTypeSettingRepository(db),new JdbcUserDirectoryRepository(db),permissions,events,view);
        var update=new UpdateWorkItem(repo,new JdbcStatusRepository(db),new JdbcPriorityRepository(db),new JdbcUserDirectoryRepository(db),permissions,events,view);
        controller=new PlanningController(db,access,items,create,update,changes,new IntegrationController(db,access,items,changes,create));
    }
    Map<String,Object> plan(long version) {
        return new LinkedHashMap<>(Map.of("version",version,"title","Published project","epics",List.of(Map.of("externalId","epic-1","title","Epic","tasks",List.of(Map.of("externalId","task-1","title","Task","plannedHours",8))))));
    }
    Map<?,?> publish(Map<String,Object> body) {return (Map<?,?>)tx.execute(s->controller.publish("external-project",body));}
    @Test void localAndPublishedProjectsCoexistAndRetriesAreIdempotent() {
        var local=tx.execute(s->items.createAs(Map.of("type","PROJECT","title","Local project"),"lead",null));
        var first=publish(plan(1));
        assertEquals("applied",first.get("status"));
        assertEquals("already-applied",publish(plan(1)).get("status"));
        assertEquals(4,db.queryForObject("SELECT count(*) FROM work_item",Integer.class));
        assertNotEquals(local.get("id"),first.get("id"));
        assertThrows(ApiException.class,()->publish(plan(0)));
        var conflict=plan(1);conflict.put("title","Conflicting");
        assertThrows(ApiException.class,()->publish(conflict));
        var next=plan(2);next.put("title","New title");publish(next);
        assertEquals("New title",items.raw((UUID)first.get("id")).get("title"));
        assertTrue(db.queryForObject("SELECT count(*)>0 FROM event_outbox",Boolean.class));
    }
    @Test void invalidPackagesRollbackAndRetirementPreservesHistoryAndFacts() {
        var invalid=plan(1);invalid.put("epics",List.of(Map.of("externalId","e","title","Epic","tasks",List.of(Map.of("externalId","t","title","Bad","plannedHours",-1)))));
        assertThrows(ApiException.class,()->publish(invalid));
        assertEquals(0,db.queryForObject("SELECT count(*) FROM work_item",Integer.class));
        var receipt=publish(plan(1));
        UUID task=db.queryForObject("SELECT work_item_id FROM planning_binding WHERE external_id='task-1'",UUID.class);
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,created_at) VALUES(?,?,'member',current_date,2,now())",UUID.randomUUID(),task);
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->tx.execute(s->db.update("UPDATE work_item SET title='Forbidden' WHERE id=?",task)));
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->tx.execute(s->db.update("DELETE FROM work_item WHERE id=?",task)));
        tx.executeWithoutResult(s->db.update("UPDATE work_item SET description='Operational description' WHERE id=?",task));
        tx.execute(s->controller.retire("external-project",2));
        assertEquals(3,db.queryForObject("SELECT count(*) FROM work_item",Integer.class));
        assertEquals(1,db.queryForObject("SELECT count(*) FROM time_log_entry",Integer.class));
        assertEquals(receipt.get("id"),db.queryForObject("SELECT work_item_id FROM planning_publication",UUID.class));
        var facts=(Map<?,?>)controller.facts("external-project",Map.of());
        assertEquals(3,((List<?>)facts.get("items")).size());
    }
    @Test void onlyPlanningServiceCanPublishOrRetire() {
        when(access.clientRole("planning-service")).thenReturn(false);
        assertThrows(ApiException.class,()->publish(plan(1)));
        assertThrows(ApiException.class,()->controller.retire("external-project",2));
        assertThrows(ApiException.class,()->controller.facts("external-project",Map.of()));
    }
}
