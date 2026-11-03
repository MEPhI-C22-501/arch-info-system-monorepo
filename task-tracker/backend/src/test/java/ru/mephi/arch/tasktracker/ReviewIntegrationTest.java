package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.core.io.ClassPathResource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.*;
import ru.mephi.arch.tasktracker.domain.event.WorkItemCreated;
import java.util.*;
import java.nio.charset.StandardCharsets;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import static org.junit.jupiter.api.Assertions.*;

@Testcontainers
class ReviewIntegrationTest {
    @Container static final PostgreSQLContainer<?> POSTGRES=new PostgreSQLContainer<>("postgres:18-alpine");
    static JdbcTemplate db;
    static TransactionTemplate tx;
    @BeforeAll static void migrate() throws Exception {
        var source=new DriverManagerDataSource(POSTGRES.getJdbcUrl(),POSTGRES.getUsername(),POSTGRES.getPassword());
        db=new JdbcTemplate(source);tx=new TransactionTemplate(new DataSourceTransactionManager(source));
        try(var connection=source.getConnection();var statement=connection.createStatement()) {
            for(String file:List.of("001-initial.sql","002-review.sql")) statement.execute(new ClassPathResource("db/changelog/"+file).getContentAsString(StandardCharsets.UTF_8));
        }
    }
    @BeforeEach void clean() { db.update("DELETE FROM notification");db.update("DELETE FROM work_item");db.update("DELETE FROM event_outbox");db.update("DELETE FROM user_cache"); }
    @Test void rollbackDoesNotLeakAnOutboxEventAndReplayKeepsItsIdentifier() {
        var outbox=new Outbox(db,"","PLAINTEXT","","","");
        var event=new WorkItemCreated(UUID.randomUUID(),"lead",null,Map.of("title","Task","type","TASK","statusId",UUID.randomUUID().toString(),"priorityId",UUID.randomUUID().toString()));
        assertThrows(IllegalStateException.class,()->tx.executeWithoutResult(s->{outbox.record(event);throw new IllegalStateException("rollback");}));
        assertEquals(0,db.queryForObject("SELECT count(*) FROM event_outbox",Integer.class));
        tx.executeWithoutResult(s->outbox.record(event));
        var id=db.queryForObject("SELECT id FROM event_outbox",UUID.class);
        db.update("UPDATE event_outbox SET state='DEAD',attempts=5");
        var access=org.mockito.Mockito.mock(AccessService.class);
        new Outbox.Admin(db,access).retry(id);
        assertEquals(id,db.queryForObject("SELECT id FROM event_outbox WHERE state='PENDING' AND attempts=0",UUID.class));
    }
    @Test void overdueNotificationsAreDeduplicatedAndAChangedDeadlineCanNotifyAgain() {
        UUID id=UUID.randomUUID();
        db.update("INSERT INTO work_item(id,type,title,status_id,priority_id,assignee_external_id,due_date,created_at,updated_at) VALUES(?,'TASK','Overdue','00000000-0000-0000-0000-000000000102','00000000-0000-0000-0000-000000000203','member',current_date-2,now(),now())",id);
        var job=new OverdueJob(db,new ChangeRecorder(db));
        tx.executeWithoutResult(s->job.run());tx.executeWithoutResult(s->job.run());
        assertEquals(1,db.queryForObject("SELECT count(*) FROM notification",Integer.class));
        db.update("UPDATE work_item SET due_date=current_date-1 WHERE id=?",id);tx.executeWithoutResult(s->job.run());
        assertEquals(2,db.queryForObject("SELECT count(*) FROM notification",Integer.class));
    }
    @Test @org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable(named="TRACKER_S3_TEST_ENDPOINT",matches=".+")
    void s3RollbackLeavesACleanupReservationAndChecksumsAreVerified() {
        String endpoint=System.getenv("TRACKER_S3_TEST_ENDPOINT");
        var credentials=software.amazon.awssdk.auth.credentials.StaticCredentialsProvider.create(software.amazon.awssdk.auth.credentials.AwsBasicCredentials.create("test","test"));
        try(var client=software.amazon.awssdk.services.s3.S3Client.builder().endpointOverride(java.net.URI.create(endpoint)).region(software.amazon.awssdk.regions.Region.US_EAST_1).credentialsProvider(credentials).forcePathStyle(true).build()) {
            client.createBucket(b->b.bucket("tracker-review"));
            var storage=new ObjectStorage(db,new DataSourceTransactionManager(db.getDataSource()),endpoint,"tracker-review","test","test");
            try {
                byte[] content="Демо-вложение".getBytes(StandardCharsets.UTF_8);
                assertThrows(IllegalStateException.class,()->tx.executeWithoutResult(status->{storage.put("rollback-file",content,"text/plain");throw new IllegalStateException("rollback");}));
                assertArrayEquals(content,storage.get("rollback-file",ObjectStorage.hash(content)));
                assertThrows(IllegalStateException.class,()->storage.get("rollback-file","wrong-checksum"));
                assertEquals(1,db.queryForObject("SELECT count(*) FROM object_cleanup WHERE object_key='rollback-file'",Integer.class));
                db.update("UPDATE object_cleanup SET after_at=now()-interval '1 second'");storage.cleanup();
                assertThrows(software.amazon.awssdk.services.s3.model.NoSuchKeyException.class,()->storage.get("rollback-file",ObjectStorage.hash(content)));
            } finally { storage.close(); }
        }
    }
    @Test @org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable(named="TRACKER_KAFKA_TEST_BOOTSTRAP",matches=".+")
    void realBrokerAcknowledgesAnOutboxEvent() {
        var outbox=new Outbox(db,System.getenv("TRACKER_KAFKA_TEST_BOOTSTRAP"),"PLAINTEXT","","","");
        try {
            var event=new WorkItemCreated(UUID.randomUUID(),"lead",null,Map.of("title","Task","type","TASK","statusId",UUID.randomUUID().toString(),"priorityId",UUID.randomUUID().toString()));
            tx.executeWithoutResult(status->outbox.record(event));
            tx.executeWithoutResult(status->outbox.send());
            assertEquals("SENT",db.queryForObject("SELECT state FROM event_outbox",String.class));
        } finally {outbox.close();}
    }
    @Test void failedSecondDirectoryPagePreservesPreviousUsers() throws Exception {
        db.update("INSERT INTO user_cache(external_user_id,display_name,active,synced_at) VALUES('existing','Existing',true,now())");
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/v1/employees/",exchange->{
            boolean second=exchange.getRequestURI().getQuery().contains("pageToken");
            byte[] body=(second?"{}":"{\"employees\":[],\"nextPageToken\":\"next\"}").getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(second?500:200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });server.start();
        try {
            var service=new DirectoryService(db,tx,"http://127.0.0.1:"+server.getAddress().getPort(),"",false);
            assertThrows(ApiException.class,service::sync);
            assertEquals(1,db.queryForObject("SELECT count(*) FROM user_cache WHERE external_user_id='existing' AND active",Integer.class));
        } finally { server.stop(0); }
    }
}
