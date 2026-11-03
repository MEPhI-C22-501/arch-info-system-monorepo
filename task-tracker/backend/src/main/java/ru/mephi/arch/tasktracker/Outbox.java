package ru.mephi.arch.tasktracker;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.apache.kafka.clients.producer.*;
import ru.mephi.arch.tasktracker.domain.event.*;
import java.time.OffsetDateTime;
import java.util.*;
import java.util.concurrent.TimeUnit;

@Component
public class Outbox {
    private final JdbcTemplate db;
    private final ObjectMapper json=new ObjectMapper().findAndRegisterModules();
    private final KafkaProducer<String,String> producer;
    public Outbox(JdbcTemplate db,@Value("${KAFKA_BOOTSTRAP_SERVERS:}") String bootstrap,
            @Value("${KAFKA_SECURITY_PROTOCOL:PLAINTEXT}") String protocol,
            @Value("${KAFKA_SASL_JAAS_CONFIG:}") String jaas,
            @Value("${KAFKA_SSL_TRUSTSTORE_LOCATION:}") String truststore,
            @Value("${KAFKA_SSL_TRUSTSTORE_PASSWORD:}") String password) {
        this.db=db;
        if(bootstrap.isBlank()) { producer=null; return; }
        Properties p=new Properties(); p.put("bootstrap.servers",bootstrap); p.put("key.serializer","org.apache.kafka.common.serialization.StringSerializer");
        p.put("value.serializer","org.apache.kafka.common.serialization.StringSerializer"); p.put("acks","all"); p.put("enable.idempotence","true");
        p.put("security.protocol",protocol); p.put("delivery.timeout.ms",10000); p.put("request.timeout.ms",5000); p.put("max.block.ms",5000);
        if(!jaas.isBlank()) { p.put("sasl.mechanism","SCRAM-SHA-512"); p.put("sasl.jaas.config",jaas); }
        if(!truststore.isBlank()) { p.put("ssl.truststore.location",truststore); p.put("ssl.truststore.password",password); }
        producer=new KafkaProducer<>(p);
    }
    @EventListener public void record(DomainEvent event) {
        try {
            Map<String,Object> payload=json.convertValue(event,new com.fasterxml.jackson.core.type.TypeReference<Map<String,Object>>() {});
            Object aggregate=payload.getOrDefault("workItemId",payload.getOrDefault("iterationId",payload.getOrDefault("workItemPublicId","system")));
            String eventType=event.getClass().getSimpleName();
            if(event instanceof RecordableChange change) {
                if(event instanceof WorkItemCreated) payload=new LinkedHashMap<>(change.newValues());
                else if(event instanceof TimeLogged) {
                    UUID timeId=UUID.fromString(change.newValues().get("timeLogAdded").toString());
                    var row=db.queryForMap("SELECT * FROM time_log_entry WHERE id=?",timeId);
                    payload=new LinkedHashMap<>();payload.put("timeLogId",timeId);payload.put("userId",row.get("external_user_id"));payload.put("hours",row.get("hours"));payload.put("loggedDate",row.get("logged_date").toString());
                } else {
                    eventType="WorkItemFieldsChanged"; payload=new LinkedHashMap<>();
                    Map<String,Object> oldDiff=new LinkedHashMap<>(),newDiff=new LinkedHashMap<>();
                    for(String field:change.newValues().keySet()) if(!Objects.equals(change.oldValues().get(field),change.newValues().get(field))) {oldDiff.put(field,change.oldValues().get(field));newDiff.put(field,change.newValues().get(field));}
                    if(newDiff.isEmpty()) return;
                    payload.put("changedFields",new ArrayList<>(newDiff.keySet()));payload.put("oldValues",oldDiff);payload.put("newValues",newDiff);
                    payload.put("version",db.queryForObject("SELECT version FROM work_item WHERE id=?",Long.class,change.workItemId()));
                }
            } else if(event instanceof IterationActivated || event instanceof IterationCompleted) {
                boolean activated=event instanceof IterationActivated;
                String snapshot=db.queryForObject("SELECT "+(activated?"baseline_snapshot":"result_snapshot")+" FROM iteration WHERE id=?",String.class,UUID.fromString(aggregate.toString()));
                payload=new LinkedHashMap<>();payload.put("iterationId",aggregate);payload.put(activated?"baselineVersion":"resultVersion",1);payload.put(activated?"baseline":"result",json.readValue(snapshot,Map.class));
            } else if(event instanceof WorkItemHardDeleted deleted) {
                payload=new LinkedHashMap<>();payload.put("workItemId",deleted.workItemPublicId());payload.put("title",deleted.title());payload.put("type",deleted.type());
            }
            Map<String,Object> envelope=new LinkedHashMap<>(); UUID id=UUID.randomUUID();
            envelope.put("eventId",id); envelope.put("eventType",eventType); envelope.put("aggregateId",aggregate);
            envelope.put("occurredAt",OffsetDateTime.now().toString()); envelope.put("correlationId",ApiAdvice.correlationId());
            envelope.put("actor",event instanceof RecordableChange change?change.actorId():json.convertValue(event,Map.class).get("actorId")); envelope.put("payload",payload);
            db.queryForObject("SELECT pg_advisory_xact_lock(hashtextextended(?,19))",Object.class,aggregate.toString());
            db.update("INSERT INTO event_outbox(id,aggregate_id,payload) VALUES(?,?,?)",id,aggregate.toString(),json.writeValueAsString(envelope));
        } catch(Exception ex) { throw new IllegalStateException("outbox_encode_failed",ex); }
    }
    @Scheduled(fixedDelay=5000) @Transactional public void send() {
        if(producer==null) return;
        var rows=db.queryForList("SELECT * FROM event_outbox e WHERE state='PENDING' AND next_attempt<=now() AND NOT EXISTS(SELECT 1 FROM event_outbox earlier WHERE earlier.aggregate_id=e.aggregate_id AND earlier.seq<e.seq AND earlier.state<>'SENT') ORDER BY seq LIMIT 20 FOR UPDATE SKIP LOCKED");
        for(var row:rows) {
            try {
                producer.send(new ProducerRecord<>("task-tracker.events.v1",row.get("aggregate_id").toString(),row.get("payload").toString())).get(12,TimeUnit.SECONDS);
                db.update("UPDATE event_outbox SET state='SENT',error=NULL WHERE id=?",row.get("id"));
            } catch(Exception ex) {
                int attempts=((Number)row.get("attempts")).intValue()+1;
                db.update("UPDATE event_outbox SET attempts=?,state=?,error=?,next_attempt=now() + interval '30 seconds' WHERE id=?",attempts,attempts>=5?"DEAD":"PENDING",ex.getClass().getSimpleName(),row.get("id"));
            }
        }
    }
    @jakarta.annotation.PreDestroy public void close() { if(producer!=null) producer.close(java.time.Duration.ofSeconds(5)); }
    @RestController @RequestMapping("/api/v1/admin/outbox")
    public static class Admin {
        private final JdbcTemplate db; private final AccessService access;
        public Admin(JdbcTemplate db,AccessService access) { this.db=db; this.access=access; }
        @GetMapping public Object list() { access.require("access.admin"); return db.queryForList("SELECT id,aggregate_id,state,attempts,error FROM event_outbox WHERE state<>'SENT' ORDER BY seq LIMIT 100"); }
        @PostMapping("/{id}/retry") public void retry(@PathVariable UUID id) { access.require("access.admin"); db.update("UPDATE event_outbox SET state='PENDING',attempts=0,next_attempt=now() WHERE id=? AND state='DEAD'",id); }
    }
}
