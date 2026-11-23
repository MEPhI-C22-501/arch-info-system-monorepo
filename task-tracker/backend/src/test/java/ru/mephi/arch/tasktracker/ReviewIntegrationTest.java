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
import org.apache.kafka.clients.producer.MockProducer;
import org.apache.kafka.common.errors.TimeoutException;
import org.apache.kafka.common.serialization.StringSerializer;
import liquibase.Contexts;
import liquibase.LabelExpression;
import liquibase.Liquibase;
import liquibase.database.DatabaseFactory;
import liquibase.database.jvm.JdbcConnection;
import liquibase.resource.ClassLoaderResourceAccessor;
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
        var source=database(POSTGRES.getDatabaseName());
        db=new JdbcTemplate(source);tx=new TransactionTemplate(new DataSourceTransactionManager(source));
        try (var migration = liquibase(source)) {
            migration.update(new Contexts(), new LabelExpression());
        }
    }
    private static DriverManagerDataSource database(String name) {
        String url = "jdbc:postgresql://%s:%d/%s".formatted(POSTGRES.getHost(), POSTGRES.getMappedPort(5432), name);
        return new DriverManagerDataSource(url, POSTGRES.getUsername(), POSTGRES.getPassword());
    }
    private static Liquibase liquibase(DriverManagerDataSource source) throws Exception {
        var database = DatabaseFactory.getInstance().findCorrectDatabaseImplementation(new JdbcConnection(source.getConnection()));
        return new Liquibase("db/changelog/db.changelog-master.yaml", new ClassLoaderResourceAccessor(), database);
    }
    @Test void baselinePreservesDataInAnExactInitialSchemaWithoutMigrationHistory() throws Exception {
        db.execute("CREATE DATABASE tracker_legacy");
        var source = database("tracker_legacy");
        var legacy = new JdbcTemplate(source);
        legacy.execute(new ClassPathResource("db/changelog/001-initial.sql").getContentAsString(StandardCharsets.UTF_8));
        legacy.update("INSERT INTO status VALUES (?, 'Legacy status', 99, true, true, 'OPEN')", UUID.randomUUID());
        try (var migration = liquibase(source)) {
            migration.changeLogSync("task-tracker-001", new Contexts(), new LabelExpression());
            assertEquals(2, legacy.queryForObject("SELECT count(*) FROM databasechangelog", Integer.class));
            migration.update(new Contexts(), new LabelExpression());
        }
        assertEquals(1, legacy.queryForObject("SELECT count(*) FROM status WHERE name='Legacy status'", Integer.class));
        assertCurrentSchema(legacy);
    }
    @Test void cleanDatabaseHasAllChangesAndNoLegacyAccessTable() {
        assertCurrentSchema(db);
    }
    private static void assertCurrentSchema(JdbcTemplate database) {
        assertEquals(5, database.queryForObject("SELECT count(*) FROM databasechangelog", Integer.class));
        assertTrue(database.queryForObject("SELECT to_regclass('planning_binding') IS NOT NULL", Boolean.class));
        assertTrue(database.queryForObject("SELECT to_regclass('local_access') IS NULL", Boolean.class));
    }
    @BeforeEach void clean() { db.update("DELETE FROM notification");db.update("DELETE FROM work_item");db.update("DELETE FROM event_outbox");db.update("DELETE FROM user_cache"); }
    @Test void iterationSnapshotsAndOutboxSupportTaskDatesWhenStartingAndCompleting() {
        var iterations = new ru.mephi.arch.tasktracker.infrastructure.persistence.JdbcIterationRepository(db);
        UUID id = UUID.randomUUID();
        var day = java.time.LocalDate.of(2026, 11, 22);
        var now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC);
        iterations.insert(new ru.mephi.arch.tasktracker.domain.iteration.Iteration(id, "Dates regression", "", day, day,
            ru.mephi.arch.tasktracker.domain.iteration.IterationState.PLANNED, now));
        var snapshot = Map.<String, Object>of("plannedHours", 8, "items", List.of(Map.of("startDate", day, "dueDate", day, "createdAt", now)));
        var outbox = new Outbox(db, "", "PLAINTEXT", "", "", "");
        tx.executeWithoutResult(status -> {
            iterations.activate(id, snapshot);
            outbox.record(new ru.mephi.arch.tasktracker.domain.event.IterationActivated(id, "lead"));
        });
        var saved = iterations.findBaselineSnapshot(id).orElseThrow();
        var item = (Map<?, ?>) ((List<?>) saved.get("items")).getFirst();
        assertEquals(day.toString(), item.get("startDate"));
        assertInstanceOf(String.class, item.get("createdAt"));
        tx.executeWithoutResult(status -> {
            iterations.complete(id, Map.of("baseline", saved, "actual", snapshot));
            outbox.record(new ru.mephi.arch.tasktracker.domain.event.IterationCompleted(id, "lead"));
        });
        assertEquals(ru.mephi.arch.tasktracker.domain.iteration.IterationState.COMPLETED, iterations.getById(id).state);
        assertTrue(iterations.findResultSnapshot(id).isPresent());
        assertEquals(2, db.queryForObject("SELECT count(*) FROM event_outbox WHERE aggregate_id=?", Integer.class, id.toString()));
    }
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
    @Test void failedDeliveryAndRestartPreserveAggregateOrderAndSkipAcknowledgedEvents() {
        UUID item = UUID.randomUUID();
        var firstProducer = new MockProducer<>(true, null, new StringSerializer(), new StringSerializer());
        firstProducer.sendException = new TimeoutException("broker unavailable");
        var firstRun = new Outbox(db, firstProducer);
        tx.executeWithoutResult(status -> {
            for (String title : List.of("First", "Second")) {
                firstRun.record(new WorkItemCreated(item, "lead", null, Map.of("title", title, "type", "TASK")));
            }
        });
        var initialPayloads = db.queryForList("SELECT payload FROM event_outbox ORDER BY seq", String.class);
        tx.executeWithoutResult(status -> firstRun.send());
        assertEquals(List.of(1, 0), db.queryForList("SELECT attempts FROM event_outbox ORDER BY seq", Integer.class));
        assertEquals(List.of("PENDING", "PENDING"), db.queryForList("SELECT state FROM event_outbox ORDER BY seq", String.class));
        firstRun.close();

        db.update("UPDATE event_outbox SET next_attempt=now() WHERE attempts=1");
        var recoveredProducer = new MockProducer<>(true, null, new StringSerializer(), new StringSerializer());
        var resumed = new Outbox(db, recoveredProducer);
        tx.executeWithoutResult(status -> resumed.send());
        assertEquals(List.of("SENT", "PENDING"), db.queryForList("SELECT state FROM event_outbox ORDER BY seq", String.class));
        resumed.close();

        var restartedProducer = new MockProducer<>(true, null, new StringSerializer(), new StringSerializer());
        var restarted = new Outbox(db, restartedProducer);
        tx.executeWithoutResult(status -> restarted.send());
        tx.executeWithoutResult(status -> restarted.send());
        assertEquals(List.of("SENT", "SENT"), db.queryForList("SELECT state FROM event_outbox ORDER BY seq", String.class));
        assertEquals(List.of(initialPayloads.getFirst()), recoveredProducer.history().stream().map(record -> record.value()).toList());
        assertEquals(List.of(initialPayloads.getLast()), restartedProducer.history().stream().map(record -> record.value()).toList());
        restarted.close();
    }
    @Test void unavailableS3ReturnsServiceUnavailableAndLeavesNoAttachment() throws Exception {
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            exchange.sendResponseHeaders(403, -1);
            exchange.close();
        });
        server.start();
        String endpoint = "http://127.0.0.1:" + server.getAddress().getPort();
        var storage = new ObjectStorage(db, new DataSourceTransactionManager(db.getDataSource()), endpoint, "test", "test", "test");
        try {
            var exception = assertThrows(ApiException.class, () -> storage.get("file", "hash"));
            assertEquals(503, exception.status);
            assertEquals("storage_unavailable", exception.getMessage());
            exception = assertThrows(ApiException.class, () -> storage.put("unavailable-upload", new byte[]{1}, "text/plain"));
            assertEquals(503, exception.status);
            assertEquals(1, db.queryForObject("SELECT count(*) FROM object_cleanup WHERE object_key='unavailable-upload'", Integer.class));
            assertEquals(0, db.queryForObject("SELECT count(*) FROM attachment WHERE object_key='unavailable-upload'", Integer.class));
        } finally {
            storage.close();
            server.stop(0);
        }
    }
    @Test void backlogLargerThanOneBatchContinuesOnTheNextPass() {
        var producer = new MockProducer<>(true, null, new StringSerializer(), new StringSerializer());
        var outbox = new Outbox(db, producer);
        tx.executeWithoutResult(status -> {
            for (int i = 0; i < 21; i++) {
                outbox.record(new WorkItemCreated(UUID.randomUUID(), "lead", null, Map.of("title", "Queued task", "type", "TASK")));
            }
        });
        tx.executeWithoutResult(status -> outbox.send());
        assertEquals(20, producer.history().size());
        assertEquals(1, db.queryForObject("SELECT count(*) FROM event_outbox WHERE state='PENDING'", Integer.class));
        tx.executeWithoutResult(status -> outbox.send());
        assertEquals(21, producer.history().size());
        assertEquals(0, db.queryForObject("SELECT count(*) FROM event_outbox WHERE state='PENDING'", Integer.class));
        outbox.close();
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
        String secret = System.getenv().getOrDefault("TRACKER_S3_TEST_SECRET", "test");
        String bucket = "tracker-review-" + UUID.randomUUID();
        var credentials=software.amazon.awssdk.auth.credentials.StaticCredentialsProvider.create(software.amazon.awssdk.auth.credentials.AwsBasicCredentials.create("test",secret));
        try(var client=software.amazon.awssdk.services.s3.S3Client.builder().endpointOverride(java.net.URI.create(endpoint)).region(software.amazon.awssdk.regions.Region.US_EAST_1).credentialsProvider(credentials).forcePathStyle(true).build()) {
            client.createBucket(b->b.bucket(bucket));
            var storage=new ObjectStorage(db,new DataSourceTransactionManager(db.getDataSource()),endpoint,bucket,"test",secret);
            try {
                byte[] content="Демо-вложение".getBytes(StandardCharsets.UTF_8);
                assertThrows(IllegalStateException.class,()->tx.executeWithoutResult(status->{storage.put("rollback-file",content,"text/plain");throw new IllegalStateException("rollback");}));
                assertArrayEquals(content,storage.get("rollback-file",ObjectStorage.hash(content)));
                assertEquals("attachment_integrity_failed", assertThrows(ApiException.class,()->storage.get("rollback-file","wrong-checksum")).getMessage());
                assertEquals(1,db.queryForObject("SELECT count(*) FROM object_cleanup WHERE object_key='rollback-file'",Integer.class));
                db.update("UPDATE object_cleanup SET after_at=now()-interval '1 second'");storage.cleanup();
                assertEquals(410, assertThrows(ApiException.class,()->storage.get("rollback-file",ObjectStorage.hash(content))).status);
            } finally {
                storage.close();
                client.deleteObject(b -> b.bucket(bucket).key("rollback-file"));
                client.deleteBucket(b -> b.bucket(bucket));
            }
        }
    }
    @Test void attachmentDeletionMakesAnExistingReservationDueImmediately() {
        UUID item = UUID.randomUUID();
        UUID attachment = UUID.randomUUID();
        db.update("INSERT INTO work_item(id,type,title,status_id,priority_id,created_at,updated_at) "
            + "VALUES(?,'TASK','With attachment','00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000203',now(),now())", item);
        db.update("INSERT INTO attachment(id,work_item_id,file_name,size_bytes,content_type,object_key,uploaded_by_external_id,uploaded_at) "
            + "VALUES(?,?,'example.txt',1,'text/plain','recent-file','lead',now())", attachment, item);
        db.update("INSERT INTO object_cleanup(object_key) VALUES('recent-file')");
        db.update("DELETE FROM work_item WHERE id=?", item);
        assertTrue(db.queryForObject("SELECT after_at <= now() FROM object_cleanup WHERE object_key='recent-file'", Boolean.class));
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
        server.createContext("/token",exchange->{
            byte[] body="{\"access_token\":\"test\"}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });
        server.createContext("/v1/profiles",exchange->{
            boolean second=exchange.getRequestURI().getQuery().contains("pageToken");
            byte[] body=(second?"{}":"{\"items\":[],\"nextPageToken\":\"next\"}").getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(second?500:200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });server.start();
        try {
            String origin="http://127.0.0.1:"+server.getAddress().getPort();
            var service=new DirectoryService(db,tx,origin,origin+"/token","test","test",false);
            assertThrows(ApiException.class,service::sync);
            assertEquals(1,db.queryForObject("SELECT count(*) FROM user_cache WHERE external_user_id='existing' AND active",Integer.class));
        } finally { server.stop(0); }
    }
    @Test void directoryReadsProfilesAndUnitsWithTrackerServiceCredentials() throws Exception {
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/token", exchange -> {
            String form = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            reply(exchange, form.equals("grant_type=client_credentials&client_id=tracker-directory&client_secret=test"),
                "{\"access_token\":\"directory-token\"}");
        });
        server.createContext("/v1/profiles", exchange -> reply(exchange,
            "Bearer directory-token".equals(exchange.getRequestHeaders().getFirst("Authorization")),
            """
            {"items":[{"userId":"staff-sub","displayName":"Employee","orgUnitId":2,
            "employmentState":"EMPLOYED","accountState":"ENABLED","isActive":true}]}
            """));
        server.createContext("/v1/org_units/", exchange -> reply(exchange,
            "Bearer directory-token".equals(exchange.getRequestHeaders().getFirst("Authorization")),
            """
            {"org_units":[{"id":1,"name":"Department","kind":"DEPARTMENT"},
            {"id":2,"name":"Team","kind":"TEAM","parent_id":1}]}
            """));
        server.start();
        try {
            String origin = "http://127.0.0.1:" + server.getAddress().getPort();
            var service = new DirectoryService(db, tx, origin, origin + "/token", "tracker-directory", "test", false);
            service.sync();
            assertEquals(Map.of("team_external_id", "2", "department_external_id", "1", "active", true),
                db.queryForMap("SELECT team_external_id,department_external_id,active FROM user_cache WHERE external_user_id='staff-sub'"));
        } finally {
            server.stop(0);
        }
    }
    private static void reply(com.sun.net.httpserver.HttpExchange exchange, boolean authorized, String body) throws java.io.IOException {
        byte[] bytes = authorized ? body.getBytes(StandardCharsets.UTF_8) : new byte[0];
        exchange.sendResponseHeaders(authorized ? 200 : 403, bytes.length);
        try (var output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }
}
