package ru.mephi.arch.tasktracker;

import org.springframework.web.bind.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.domain.event.WorkItemFieldsChanged;
import java.util.*;

@RestController
@RequestMapping("/api/v1/work-items/{id}/links")
public class LinkController {
    private final JdbcTemplate db;
    private final WorkItemRepository items;
    private final PermissionPort permissions;
    private final EventPublisherPort events;
    public LinkController(JdbcTemplate db, WorkItemRepository items, PermissionPort permissions, EventPublisherPort events) {
        this.db=db; this.items=items; this.permissions=permissions; this.events=events;
    }
    private void read(UUID id) { permissions.requireItemReadable(items.getById(id).assigneeId); }
    private void writable(UUID id) { permissions.requireItemWritable(items.getById(id).assigneeId); }
    @GetMapping public Object list(@PathVariable UUID id) {
        read(id); List<Object> result=new ArrayList<>();
        for(var row:db.queryForList("SELECT * FROM work_item_link WHERE source_id=? OR target_id=? ORDER BY id",id,id)) {
            UUID other=id.equals(row.get("source_id"))?(UUID)row.get("target_id"):(UUID)row.get("source_id");
            try { read(other); } catch(ApiException ex) { if(ex.status==403) continue; throw ex; }
            var item=items.getById(other);
            result.add(Map.of("id",row.get("id"),"targetId",other,"title",item.title,"type",row.get("type"),"outgoing",id.equals(row.get("source_id"))));
        }
        return result;
    }
    @PostMapping @Transactional public Object create(@PathVariable UUID id,@RequestBody Map<String,Object> body) {
        writable(id); UUID target=Values.requiredUuid(body,"targetId"); read(target);
        String type=Values.str(body,"type",true);
        if(!Set.of("BLOCKS","RELATED").contains(type) || id.equals(target)) throw ApiException.invalid("type","invalid_link");
        for(UUID key:List.of(id,target)) if(!Set.of("TASK","BUG","SUBTASK").contains(items.getById(key).type.name())) throw ApiException.invalid("targetId","leaf_type_required");
        db.queryForObject("SELECT pg_advisory_xact_lock(7291841)",Object.class);
        UUID source=id;
        if(type.equals("RELATED") && source.toString().compareTo(target.toString())>0) { UUID swap=source; source=target; target=swap; }
        if(type.equals("BLOCKS") && Boolean.TRUE.equals(db.queryForObject("WITH RECURSIVE path(id) AS (SELECT ?::uuid UNION SELECT l.target_id FROM work_item_link l JOIN path p ON l.source_id=p.id WHERE l.type='BLOCKS') SELECT EXISTS(SELECT 1 FROM path WHERE id=?)",Boolean.class,target,source))) throw ApiException.conflict("targetId","dependency_cycle");
        UUID link=UUID.randomUUID();
        int inserted=db.update("INSERT INTO work_item_link(id,source_id,target_id,type) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",link,source,target,type);
        if(inserted==0) throw ApiException.conflict("targetId","duplicate_link");
        items.touch(id); events.publish(new WorkItemFieldsChanged(id,permissions.currentSubject(),null,Map.of("linkAdded",false),Map.of("linkAdded",link.toString())));
        return Map.of("id",link);
    }
    @DeleteMapping("/{linkId}") @Transactional public void delete(@PathVariable UUID id,@PathVariable UUID linkId) {
        writable(id);
        var rows=db.queryForList("SELECT * FROM work_item_link WHERE id=? AND (source_id=? OR target_id=?)",linkId,id,id);
        if(rows.isEmpty()) throw ApiException.missing("linkId");
        var row=rows.getFirst(); writable((UUID)row.get("source_id"));
        read((UUID)row.get("target_id"));
        db.update("DELETE FROM work_item_link WHERE id=?",linkId); items.touch(id);
        events.publish(new WorkItemFieldsChanged(id,permissions.currentSubject(),null,Map.of("linkRemoved",false),Map.of("linkRemoved",linkId.toString())));
    }
}
