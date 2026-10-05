package ru.mephi.arch.tasktracker;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.*;

@Service
public class ChangeRecorder {
    private final JdbcTemplate db;
    private final ObjectMapper json = new ObjectMapper().findAndRegisterModules();
    public ChangeRecorder(JdbcTemplate db) { this.db = db; }
    public String json(Object value) {
        try { return json.writeValueAsString(value); }
        catch (JsonProcessingException e) { throw new IllegalStateException(e); }
    }
    @SuppressWarnings("unchecked")
    public Map<String,Object> parseMap(Object value) {
        if (value == null) return Map.of();
        try { return json.readValue(value.toString(), Map.class); }
        catch (JsonProcessingException e) { throw new IllegalStateException(e); }
    }
    public void record(UUID itemId, String actor, String source, Map<String,Object> oldValues, Map<String,Object> newValues, String message) {
        Map<String,Object> oldDiff = new LinkedHashMap<>();
        Map<String,Object> newDiff = new LinkedHashMap<>();
        Set<String> fields = new LinkedHashSet<>();
        for (String key : newValues.keySet()) {
            if (!Objects.equals(oldValues.get(key), newValues.get(key))) {
                fields.add(key); oldDiff.put(key, oldValues.get(key)); newDiff.put(key, newValues.get(key));
            }
        }
        if (fields.isEmpty()) return;
        db.update("INSERT INTO audit_entry(id,work_item_id,actor_external_id,external_source,occurred_at,changed_fields,old_values,new_values) VALUES (?,?,?,?,?,CAST(? AS jsonb),CAST(? AS jsonb),CAST(? AS jsonb))",
            UUID.randomUUID(), itemId, source == null ? actor : null, source, OffsetDateTime.now(ZoneOffset.UTC), json(fields), json(oldDiff), json(newDiff));
        var item = db.queryForMap("SELECT title,assignee_external_id FROM work_item WHERE id=?", itemId);
        String assignee = (String) item.get("assignee_external_id");
        if (assignee != null) notify(assignee, itemId, itemId.toString(), (String)item.get("title"), message, actor);
    }
    public void notify(String recipient, UUID itemId, String publicId, String title, String message, String actor) {
        db.update("INSERT INTO notification(id,recipient_external_id,work_item_id,work_item_public_id,work_item_title,message,actor,created_at) VALUES (?,?,?,?,?,?,?,?)",
            UUID.randomUUID(),recipient,itemId,publicId,title,message,actor,OffsetDateTime.now(ZoneOffset.UTC));
    }
}
