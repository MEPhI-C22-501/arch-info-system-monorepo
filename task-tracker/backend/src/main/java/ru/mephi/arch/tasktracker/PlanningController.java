package ru.mephi.arch.tasktracker;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import ru.mephi.arch.tasktracker.application.workitem.CreateWorkItem;
import ru.mephi.arch.tasktracker.application.workitem.UpdateWorkItem;
import java.util.*;

/** Projects created locally and published projects coexist; only explicit IDs establish a binding. */
@RestController
@RequestMapping("/api/v1/planning/projects")
public class PlanningController {
    private final JdbcTemplate db;
    private final AccessService access;
    private final WorkItemService items;
    private final CreateWorkItem create;
    private final UpdateWorkItem update;
    private final ChangeRecorder json;
    private final IntegrationController reports;
    public PlanningController(JdbcTemplate db, AccessService access, WorkItemService items, CreateWorkItem create,
                              UpdateWorkItem update, ChangeRecorder json, IntegrationController reports) {
        this.db=db; this.access=access; this.items=items; this.create=create; this.update=update; this.json=json; this.reports=reports;
    }
    private void authorize() {
        if (!access.clientRole("planning-service")) throw new ApiException(403,"scope","insufficient_scope");
    }
    private void lock(String externalId) {
        if (externalId.isBlank() || externalId.contains(":")) throw ApiException.invalid("externalId","invalid");
        db.queryForObject("SELECT pg_advisory_xact_lock(hashtextextended(?,31))",Object.class,externalId);
    }
    private List<Map<String,Object>> publication(String externalId) {
        return db.queryForList("SELECT * FROM planning_publication WHERE external_id=?",externalId);
    }
    private long version(Object input) {
        long value=Values.version(input);
        if(value==0) throw ApiException.invalid("version","must_be_positive");
        return value;
    }
    private List<Map<String,Object>> children(Map<String,Object> input,String field) {
        if (!(input.get(field) instanceof List<?> rows)) throw ApiException.invalid(field,"required_array");
        var result=new ArrayList<Map<String,Object>>();
        for(Object row:rows) {
            if(!(row instanceof Map<?,?> map)) throw ApiException.invalid(field,"invalid_object");
            Map<String,Object> entry=new LinkedHashMap<>();
            map.forEach((k,v)->entry.put(k.toString(),v)); result.add(entry);
        }
        return result;
    }
    @PutMapping("/{externalId}") @Transactional
    public Object publish(@PathVariable String externalId,@RequestBody Map<String,Object> body) {
        authorize(); lock(externalId);
        long version=version(body.get("version"));
        String document=json.json(body);
        var previous=publication(externalId);
        if(!previous.isEmpty()) {
            var old=previous.getFirst(); long oldVersion=((Number)old.get("version")).longValue();
            boolean identical=Boolean.TRUE.equals(db.queryForObject("SELECT document=CAST(? AS jsonb) FROM planning_publication WHERE external_id=?",Boolean.class,document,externalId));
            if(version==oldVersion && identical && !Boolean.TRUE.equals(old.get("retired"))) return receipt(externalId,old.get("work_item_id"),version,"already-applied");
            if(version<=oldVersion) throw ApiException.conflict("version","stale_or_conflicting_publication");
        }
        db.queryForObject("SELECT set_config('app.planning_write','true',true)",String.class);
        Set<String> externalIds=new HashSet<>();
        UUID project=apply(externalId,externalId,"PROJECT",null,body,externalIds);
        if(previous.isEmpty()) db.update("INSERT INTO planning_publication(external_id,work_item_id,version,document) VALUES(?,?,?,CAST(? AS jsonb))",externalId,project,version,document);
        else db.update("UPDATE planning_publication SET version=?,document=CAST(? AS jsonb),retired=false WHERE external_id=?",version,document,externalId);
        bind(externalId,externalId,project);
        for(var epic:children(body,"epics")) {
            String epicId=Values.str(epic,"externalId",true);
            UUID localEpic=apply(externalId,epicId,"EPIC",project,epic,externalIds);
            bind(externalId,epicId,localEpic);
            for(var task:children(epic,"tasks")) {
                String taskId=Values.str(task,"externalId",true);
                UUID localTask=apply(externalId,taskId,"TASK",localEpic,task,externalIds);
                bind(externalId,taskId,localTask);
            }
        }
        db.queryForObject("SELECT set_config('app.planning_write','false',true)",String.class);
        return receipt(externalId,project,version,"applied");
    }
    private UUID apply(String project,String external,String type,UUID parent,Map<String,Object> input,Set<String> seen) {
        if(external.isBlank() || external.contains(":") || !seen.add(external)) throw ApiException.invalid("externalId","duplicate_or_invalid");
        var existing=db.queryForList("SELECT work_item_id FROM planning_binding WHERE project_external_id=? AND external_id=?",project,external);
        UUID explicit=Values.uuid(input.get("localWorkItemId"),"localWorkItemId");
        UUID id=existing.isEmpty()?explicit:(UUID)existing.getFirst().get("work_item_id");
        if(!existing.isEmpty() && explicit!=null && !explicit.equals(id)) throw ApiException.conflict("localWorkItemId","binding_immutable");
        Map<String,Object> fields=new LinkedHashMap<>();
        fields.put("title",Values.str(input,"title",true)); fields.put("parentId",parent);
        for(String field:List.of("assigneeId","startDate","dueDate")) fields.put(field,input.get(field));
        fields.put("plannedHours","TASK".equals(type)?input.get("plannedHours"):null);
        if(id==null) {
            fields.put("type",type);
            return (UUID)create.execute(fields,access.subject(),"planning-system").get("id");
        }
        if (db.queryForList("SELECT id FROM work_item WHERE id=? FOR UPDATE", id).isEmpty()) {
            throw ApiException.missing("localWorkItemId");
        }
        var other=db.queryForList("SELECT project_external_id,external_id FROM planning_binding WHERE work_item_id=?",id);
        if(!other.isEmpty() && (!project.equals(other.getFirst().get("project_external_id")) || !external.equals(other.getFirst().get("external_id")))) throw ApiException.conflict("localWorkItemId","already_bound");
        var item=items.raw(id);
        if(!type.equals(item.get("type"))) throw ApiException.invalid("localWorkItemId","wrong_type");
        fields.put("version",item.get("version"));
        update.execute(id,fields,access.subject(),"planning-system");
        return id;
    }
    private void bind(String project,String external,UUID local) {
        db.update("INSERT INTO planning_binding(project_external_id,external_id,work_item_id) VALUES(?,?,?) ON CONFLICT(project_external_id,external_id) DO NOTHING",project,external,local);
    }
    private Map<String,Object> receipt(String external,Object id,long version,String status) {
        return Map.of("id",id,"externalProjectId",external,"version",version,"status",status);
    }
    @DeleteMapping("/{externalId}") @Transactional
    public Object retire(@PathVariable String externalId,@RequestParam long version) {
        authorize(); lock(externalId); version(version);
        var rows=publication(externalId);
        if(rows.isEmpty()) throw ApiException.missing("externalId");
        var old=rows.getFirst(); long current=((Number)old.get("version")).longValue();
        if(version==current && Boolean.TRUE.equals(old.get("retired"))) return receipt(externalId,old.get("work_item_id"),version,"already-applied");
        if(version<=current) throw ApiException.conflict("version","stale_or_conflicting_publication");
        db.update("UPDATE planning_publication SET retired=true,version=? WHERE external_id=?",version,externalId);
        return receipt(externalId,old.get("work_item_id"),version,"applied");
    }
    @GetMapping("/{externalId}/facts")
    @Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public Object facts(@PathVariable String externalId,@RequestParam Map<String,String> filters) {
        authorize(); var rows=publication(externalId);
        if(rows.isEmpty()) throw ApiException.missing("externalId");
        var selection=new HashMap<>(filters); selection.put("projectId",rows.getFirst().get("work_item_id").toString());
        return reports.workItemPage(selection);
    }
}
