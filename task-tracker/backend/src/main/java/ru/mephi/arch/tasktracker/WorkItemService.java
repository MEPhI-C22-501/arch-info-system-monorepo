package ru.mephi.arch.tasktracker;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.sql.Date;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.*;

@Service
public class WorkItemService {
    static final UUID BACKLOG = UUID.fromString("00000000-0000-0000-0000-000000000101");
    static final UUID MEDIUM = UUID.fromString("00000000-0000-0000-0000-000000000203");
    private final JdbcTemplate db;
    private final AccessService access;
    private final ChangeRecorder changes;
    public WorkItemService(JdbcTemplate db, AccessService access, ChangeRecorder changes) {
        this.db=db; this.access=access; this.changes=changes;
    }
    public Map<String,Object> raw(UUID id) {
        var rows=db.queryForList("SELECT * FROM work_item WHERE id=?",id);
        if (rows.isEmpty()) throw ApiException.missing("workItemId");
        return rows.getFirst();
    }
    private UUID activeReference(String table, UUID id, String field) {
        if (id == null) throw ApiException.invalid(field,"required");
        Integer found=db.query("SELECT 1 FROM "+table+" WHERE id=? AND active=true",rs->rs.next()?1:null,id);
        if (found==null) throw ApiException.invalid(field,"unknown_or_inactive");
        return id;
    }
    private void assignee(String id) {
        if (id==null) return;
        Integer found=db.query("SELECT 1 FROM user_cache WHERE external_user_id=? AND active=true",rs->rs.next()?1:null,id);
        if (found==null) throw ApiException.invalid("assigneeId","unknown_or_inactive");
    }
    private void parent(UUID id, String type, UUID parentId) {
        if (parentId==null) {
            if ("EPIC".equals(type)||"SUBTASK".equals(type)) throw ApiException.invalid("parentId","required_for_type");
            return;
        }
        if (parentId.equals(id)) throw ApiException.invalid("parentId","self_parent");
        var p=raw(parentId);
        String parentType=(String)p.get("type");
        boolean valid=("EPIC".equals(type)&&"PROJECT".equals(parentType))
            || (("TASK".equals(type)||"BUG".equals(type))&&"EPIC".equals(parentType))
            || ("SUBTASK".equals(type)&&("TASK".equals(parentType)||"BUG".equals(parentType)));
        if (!valid) throw ApiException.invalid("parentId","invalid_hierarchy");
        UUID cursor=parentId;
        while(cursor!=null) {
            if(cursor.equals(id)) throw ApiException.invalid("parentId","cycle");
            cursor=(UUID)raw(cursor).get("parent_id");
        }
    }
    private void dates(LocalDate start, LocalDate due) {
        if(start!=null&&due!=null&&due.isBefore(start)) throw ApiException.invalid("dueDate","before_start_date");
    }
    private void estimate(String type, UUID id, BigDecimal planned) {
        if(planned==null) return;
        if("PROJECT".equals(type)||"EPIC".equals(type)) throw ApiException.invalid("plannedHours","parent_is_computed");
        if(id!=null && db.queryForObject("SELECT count(*) FROM work_item WHERE parent_id=?",Integer.class,id)>0)
            throw ApiException.invalid("plannedHours","parent_is_computed");
    }
    private static Date sqlDate(LocalDate date) { return date==null?null:Date.valueOf(date); }
    private static Object field(Map<String,Object> input,String key,Object fallback) { return input.containsKey(key)?input.get(key):fallback; }
    private static String nullableString(Object value) { return value==null||value.toString().isBlank()?null:value.toString().trim(); }

    @Transactional
    public Map<String,Object> create(Map<String,Object> input) {
        access.require("item.create");
        return createAs(input,access.subject(),null);
    }
    @Transactional
    public Map<String,Object> createAs(Map<String,Object> input,String actor,String source) {
        String type=Values.type(Values.str(input,"type",true));
        String title=Values.str(input,"title",true);
        Integer enabled=db.queryForObject("SELECT count(*) FROM type_setting WHERE type=? AND enabled=true",Integer.class,type);
        if(enabled==0) throw ApiException.invalid("type","disabled");
        UUID defaultStatus=db.queryForObject("SELECT id FROM status WHERE active=true AND category='OPEN' ORDER BY board_order LIMIT 1",UUID.class);
        UUID defaultPriority=db.queryForObject("SELECT id FROM priority WHERE active=true ORDER BY sort_order LIMIT 1",UUID.class);
        UUID status=activeReference("status",Values.uuid(input.getOrDefault("statusId",defaultStatus),"statusId"),"statusId");
        UUID priority=activeReference("priority",Values.uuid(input.getOrDefault("priorityId",defaultPriority),"priorityId"),"priorityId");
        UUID parentId=Values.uuid(input.get("parentId"),"parentId");
        UUID id=input.get("id")==null?UUID.randomUUID():Values.uuid(input.get("id"),"id");
        parent(id,type,parentId);
        String assignee=nullableString(input.get("assigneeId"));
        if(source==null && actor.equals(access.subject()) && "MEMBER".equals(access.role()) && assignee==null) assignee=actor;
        assignee(assignee);
        LocalDate start=Values.date(input.get("startDate"),"startDate");
        LocalDate due=Values.date(input.get("dueDate"),"dueDate");
        dates(start,due);
        BigDecimal planned=Values.hours(input.get("plannedHours"),"plannedHours",false);
        estimate(type,null,planned);
        var now=OffsetDateTime.now(ZoneOffset.UTC);
        db.update("INSERT INTO work_item(id,type,title,description,status_id,priority_id,assignee_external_id,start_date,due_date,planned_hours,parent_id,external_source,external_defect_id,severity,environment,test_run_url,test_case_url,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            id,type,title,Objects.toString(input.getOrDefault("description",""),""),status,priority,assignee,sqlDate(start),sqlDate(due),planned,parentId,
            input.get("externalSource"),input.get("externalDefectId"),input.get("severity"),input.get("environment"),input.get("testRunUrl"),input.get("testCaseUrl"),now,now);
        if(parentId!=null) {
            db.update("UPDATE work_item SET planned_hours=NULL,version=version+1,updated_at=? WHERE id=?",now,parentId);
            changes.record(parentId,actor,source,Map.of("childAdded",false),Map.of("childAdded",id.toString()),"Изменена иерархия");
        }
        Map<String,Object> auditNew=new LinkedHashMap<>();
        auditNew.put("type",type);auditNew.put("title",title);auditNew.put("statusId",status.toString());
        auditNew.put("priorityId",priority.toString());auditNew.put("assigneeId",assignee);
        if(source!=null){auditNew.put("externalSource",source);auditNew.put("externalDefectId",input.get("externalDefectId"));}
        changes.record(id,actor,source,Map.of(),auditNew,"Создан рабочий элемент");
        return view(id);
    }
    @Transactional
    public Map<String,Object> update(UUID id,Map<String,Object> input) {
        var before=raw(id); access.itemWrite(before);
        return updateAs(id,input,access.subject(),null);
    }
    @Transactional
    public Map<String,Object> updateAs(UUID id,Map<String,Object> input,String actor,String source) {
        var before=raw(id);
        if(input.containsKey("version") && Long.parseLong(input.get("version").toString())!=((Number)before.get("version")).longValue())
            throw ApiException.conflict("version","stale_work_item");
        String title=nullableString(field(input,"title",before.get("title")));
        if(title==null) throw ApiException.invalid("title","required");
        String type=(String)before.get("type");
        if(input.containsKey("type") && !type.equals(input.get("type"))) throw ApiException.invalid("type","immutable");
        UUID status=(UUID)before.get("status_id");
        if(input.containsKey("statusId")) {UUID requested=Values.uuid(input.get("statusId"),"statusId");if(!status.equals(requested))access.require("item.status");status=activeReference("status",requested,"statusId");}
        UUID priority=input.containsKey("priorityId")?activeReference("priority",Values.uuid(input.get("priorityId"),"priorityId"),"priorityId"):(UUID)before.get("priority_id");
        UUID parentId=input.containsKey("parentId")?Values.uuid(input.get("parentId"),"parentId"):(UUID)before.get("parent_id");
        parent(id,type,parentId);
        String assignee=nullableString(field(input,"assigneeId",before.get("assignee_external_id")));
        if(!Objects.equals(before.get("assignee_external_id"),assignee)) assignee(assignee);
        LocalDate start=Values.date(field(input,"startDate",before.get("start_date")),"startDate");
        LocalDate due=Values.date(field(input,"dueDate",before.get("due_date")),"dueDate");
        dates(start,due);
        BigDecimal planned=Values.hours(field(input,"plannedHours",before.get("planned_hours")),"plannedHours",false);
        estimate(type,id,planned);
        String description=Objects.toString(field(input,"description",before.get("description")),"");
        Map<String,Object> oldVals=fields(before);
        Map<String,Object> newVals=new LinkedHashMap<>();
        newVals.put("title",title);newVals.put("description",description);newVals.put("statusId",status.toString());
        newVals.put("priorityId",priority.toString());newVals.put("assigneeId",assignee);
        newVals.put("startDate",start==null?null:start.toString());newVals.put("dueDate",due==null?null:due.toString());
        newVals.put("plannedHours",planned);newVals.put("parentId",parentId==null?null:parentId.toString());
        if(oldVals.equals(newVals)) return view(id);
        db.update("UPDATE work_item SET title=?,description=?,status_id=?,priority_id=?,assignee_external_id=?,start_date=?,due_date=?,planned_hours=?,parent_id=?,version=version+1,updated_at=? WHERE id=?",
            title,description,status,priority,assignee,sqlDate(start),sqlDate(due),planned,parentId,OffsetDateTime.now(ZoneOffset.UTC),id);
        if(!Objects.equals(before.get("parent_id"),parentId)) {
            if(before.get("parent_id")!=null) {touch((UUID)before.get("parent_id"));changes.record((UUID)before.get("parent_id"),actor,source,Map.of("childRemoved",false),Map.of("childRemoved",id.toString()),"Изменена иерархия");}
            if(parentId!=null) {db.update("UPDATE work_item SET planned_hours=NULL,version=version+1,updated_at=? WHERE id=?",OffsetDateTime.now(ZoneOffset.UTC),parentId);changes.record(parentId,actor,source,Map.of("childAdded",false),Map.of("childAdded",id.toString()),"Изменена иерархия");}
        }
        changes.record(id,actor,source,oldVals,newVals,"Изменена карточка");
        return view(id);
    }
    private Map<String,Object> fields(Map<String,Object> raw) {
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("title",raw.get("title"));result.put("description",raw.get("description"));
        result.put("statusId",raw.get("status_id").toString());result.put("priorityId",raw.get("priority_id").toString());
        result.put("assigneeId",raw.get("assignee_external_id"));
        result.put("startDate",raw.get("start_date")==null?null:raw.get("start_date").toString());
        result.put("dueDate",raw.get("due_date")==null?null:raw.get("due_date").toString());
        result.put("plannedHours",raw.get("planned_hours"));
        result.put("parentId",raw.get("parent_id")==null?null:raw.get("parent_id").toString());
        return result;
    }
    public Map<String,Object> view(UUID id) {
        var w=raw(id);
        var totals=db.queryForMap("WITH RECURSIVE d AS (SELECT id,planned_hours FROM work_item WHERE id=? UNION ALL SELECT w.id,w.planned_hours FROM work_item w JOIN d ON w.parent_id=d.id), leaves AS (SELECT d.id,d.planned_hours FROM d WHERE NOT EXISTS(SELECT 1 FROM work_item c WHERE c.parent_id=d.id)) SELECT COALESCE(SUM(planned_hours),0) AS planned, (SELECT COALESCE(SUM(t.hours),0) FROM time_log_entry t JOIN leaves l ON l.id=t.work_item_id) AS actual, COUNT(*) FILTER (WHERE planned_hours IS NULL) AS unestimated FROM leaves",id);
        BigDecimal planned=(BigDecimal)totals.get("planned"),actual=(BigDecimal)totals.get("actual");
        Map<String,Object> out=new LinkedHashMap<>();
        out.put("id",id);out.put("type",w.get("type"));out.put("title",w.get("title"));out.put("description",w.get("description"));
        out.put("statusId",w.get("status_id"));out.put("priorityId",w.get("priority_id"));
        out.put("assigneeId",w.get("assignee_external_id"));out.put("startDate",w.get("start_date"));out.put("dueDate",w.get("due_date"));
        out.put("plannedHours",planned);out.put("actualHours",actual);out.put("remainingHours",planned.subtract(actual));
        out.put("unestimatedLeaves",((Number)totals.get("unestimated")).longValue());
        out.put("parentId",w.get("parent_id"));out.put("version",w.get("version"));
        out.put("createdAt",w.get("created_at"));out.put("updatedAt",w.get("updated_at"));
        out.put("externalSource",w.get("external_source"));out.put("externalDefectId",w.get("external_defect_id"));
        out.put("severity",w.get("severity"));out.put("environment",w.get("environment"));
        out.put("testRunUrl",w.get("test_run_url"));out.put("testCaseUrl",w.get("test_case_url"));
        var current=db.queryForList("SELECT wi.iteration_id FROM work_item_iteration wi JOIN iteration i ON i.id=wi.iteration_id WHERE wi.work_item_id=? AND wi.removed_at IS NULL AND i.state<>'COMPLETED' LIMIT 1",id);
        out.put("iterationId",current.isEmpty()?null:current.getFirst().get("iteration_id"));
        out.put("children",db.queryForList("SELECT id,type,title,status_id AS \"statusId\" FROM work_item WHERE parent_id=? ORDER BY created_at",id));
        return out;
    }
    public Map<String,Object> read(UUID id) { access.itemRead(raw(id)); return view(id); }
    public Map<String,Object> list(Map<String,String> filters) {
        access.require("item.read");
        int page=Math.max(1,parseInt(filters.get("page"),1));int size=Math.min(500,Math.max(1,parseInt(filters.get("pageSize"),50)));
        StringBuilder where=new StringBuilder(" WHERE 1=1"); List<Object> args=new ArrayList<>();
        for(var e:Map.of("type","w.type","statusId","w.status_id","priorityId","w.priority_id","assigneeId","w.assignee_external_id").entrySet()) {
            String value=filters.get(e.getKey());if(value!=null&&!value.isBlank()){where.append(" AND ").append(e.getValue()).append("=?");args.add(e.getKey().endsWith("Id")&&!e.getKey().equals("assigneeId")?Values.uuid(value,e.getKey()):value);}
        }
        if(filters.get("iterationId")!=null&&!filters.get("iterationId").isBlank()) {where.append(" AND EXISTS (SELECT 1 FROM work_item_iteration wi WHERE wi.work_item_id=w.id AND wi.iteration_id=? AND wi.removed_at IS NULL)");args.add(Values.uuid(filters.get("iterationId"),"iterationId"));}
        if("MEMBER".equals(access.role())) {where.append(" AND w.assignee_external_id=?");args.add(access.subject());}
        if(filters.get("search")!=null&&!filters.get("search").isBlank()){where.append(" AND lower(w.title) LIKE ?");args.add("%"+filters.get("search").toLowerCase()+"%");}
        String base=" FROM work_item w JOIN status s ON s.id=w.status_id JOIN priority p ON p.id=w.priority_id"+where;
        long total=db.queryForObject("SELECT count(*)"+base,Long.class,args.toArray());
        String sort= switch(Objects.toString(filters.get("sort"),"dueDate")) {
            case "priority" -> "p.sort_order,w.created_at";case "status" -> "s.board_order,w.created_at";
            case "createdAt" -> "w.created_at DESC";default -> "w.due_date NULLS LAST,w.created_at";};
        var queryArgs=new ArrayList<>(args);queryArgs.add(size);queryArgs.add((page-1)*size);
        var ids=db.queryForList("SELECT w.id"+base+" ORDER BY "+sort+" LIMIT ? OFFSET ?",UUID.class,queryArgs.toArray());
        return Map.of("items",ids.stream().map(this::view).toList(),"page",page,"pageSize",size,"totalPages",(total+size-1)/size,"total",total);
    }
    private int parseInt(String value,int fallback){try{return value==null?fallback:Integer.parseInt(value);}catch(NumberFormatException e){throw ApiException.invalid("page","invalid_integer");}}
    @Transactional
    public void delete(UUID id,String confirmation) {
        access.require("item.delete");
        if(!id.toString().equals(confirmation)) throw ApiException.invalid("confirmationId","confirmation_required");
        var item=raw(id);
        if(db.queryForObject("SELECT count(*) FROM work_item WHERE parent_id=?",Integer.class,id)>0) throw ApiException.conflict("children","move_or_delete_children_first");
        UUID parentId=(UUID)item.get("parent_id");
        db.update("DELETE FROM work_item WHERE id=?",id);
        if(parentId!=null) {touch(parentId);changes.record(parentId,access.subject(),null,Map.of("childRemoved",false),Map.of("childRemoved",id.toString()),"Удалён дочерний элемент");}
        if(item.get("assignee_external_id")!=null) changes.notify((String)item.get("assignee_external_id"),null,id.toString(),(String)item.get("title"),"Рабочий элемент удалён",access.subject());
    }
    public List<Map<String,Object>> history(UUID id) {
        access.itemRead(raw(id));
        return db.queryForList("SELECT id,actor_external_id AS \"actorId\",external_source AS \"externalSource\",occurred_at AS \"occurredAt\",changed_fields AS \"changedFields\",old_values AS \"oldValues\",new_values AS \"newValues\" FROM audit_entry WHERE work_item_id=? ORDER BY occurred_at,id",id);
    }
    public void touch(UUID id) {db.update("UPDATE work_item SET version=version+1,updated_at=? WHERE id=?",OffsetDateTime.now(ZoneOffset.UTC),id);}
}
