package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import java.net.URI;
import java.time.LocalDate;
import java.util.*;

@RestController @RequestMapping("/api/v1")
public class IntegrationController {
    private final JdbcTemplate db;private final AccessService access;private final WorkItemService items;private final ChangeRecorder changes;
    public IntegrationController(JdbcTemplate db,AccessService access,WorkItemService items,ChangeRecorder changes){this.db=db;this.access=access;this.items=items;this.changes=changes;}
    @PostMapping("/bugs") @Transactional public ResponseEntity<?> bug(@RequestBody Map<String,Object> body){
        access.testing();String source=Values.str(body,"externalSource",true),external=Values.str(body,"externalDefectId",true);
        String title=Values.str(body,"title",true),description=Values.str(body,"description",true),severity=Values.str(body,"severity",true).toLowerCase(Locale.ROOT);
        if(!Set.of("critical","high","medium","low").contains(severity))throw ApiException.invalid("severity","invalid");
        if(blank(body.get("environment"))&&blank(body.get("build")))throw ApiException.invalid("environment","environment_or_build_required");
        if(blank(body.get("testRunUrl"))&&blank(body.get("testCaseUrl")))throw ApiException.invalid("testRunUrl","test_link_required");
        db.queryForObject("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",Object.class,source+":"+external);
        var existing=db.queryForList("SELECT id FROM work_item WHERE external_source=? AND external_defect_id=?",source,external);
        if(!existing.isEmpty()){UUID id=(UUID)existing.getFirst().get("id");return ResponseEntity.ok(Map.of("id",id,"status","already-exists","workItemUrl","/work-items/"+id));}
        UUID priority=db.query("SELECT p.id FROM severity_priority sp JOIN priority p ON p.id=sp.priority_id WHERE sp.severity=? AND p.active=true",rs->rs.next()?(UUID)rs.getObject(1):null,severity);
        if(priority==null)throw ApiException.invalid("severity","priority_mapping_unavailable");
        Map<String,Object> request=new LinkedHashMap<>();request.put("type","BUG");request.put("title",title);request.put("description",description);
        request.put("priorityId",priority);request.put("externalSource",source);request.put("externalDefectId",external);request.put("severity",severity);
        request.put("environment",Objects.toString(body.getOrDefault("environment",body.get("build")),""));request.put("testRunUrl",body.get("testRunUrl"));request.put("testCaseUrl",body.get("testCaseUrl"));
        var created=items.createAs(request,access.subject(),source);UUID id=(UUID)created.get("id");
        return ResponseEntity.created(URI.create("/api/v1/work-items/"+id)).body(Map.of("id",id,"status","created","workItemUrl","/work-items/"+id));
    }
    private boolean blank(Object value){return value==null||value.toString().isBlank();}
    @GetMapping("/reports/work-items") public Object reportItems(@RequestParam Map<String,String> filters){
        access.reports();int page=page(filters.get("page"),1),size=Math.min(500,page(filters.get("pageSize"),100));
        LocalDate from=Values.date(filters.get("periodFrom"),"periodFrom"),to=Values.date(filters.get("periodTo"),"periodTo");
        if(from!=null&&to!=null&&to.isBefore(from))throw ApiException.invalid("periodTo","before_periodFrom");
        List<Map<String,Object>> output=new ArrayList<>();
        for(UUID id:db.queryForList("SELECT id FROM work_item ORDER BY id",UUID.class)){
            var item=items.view(id);UUID project=projectId(id);var raw=items.raw(id);
            UUID iteration=reportIterationId(id);
            if(!match(filters,"projectId",project)||!iterationMatches(filters.get("iterationId"),id)||!match(filters,"type",item.get("type"))||!match(filters,"assigneeId",item.get("assigneeId")))continue;
            var status=db.queryForMap("SELECT name FROM status WHERE id=?",item.get("statusId"));
            if(filters.get("status")!=null&&!filters.get("status").equals(status.get("name"))&&!filters.get("status").equals(item.get("statusId").toString()))continue;
            LocalDate changed=((java.sql.Timestamp)raw.get("updated_at")).toLocalDateTime().toLocalDate();
            if(from!=null&&changed.isBefore(from)||to!=null&&changed.isAfter(to))continue;
            Map<String,Object> row=new LinkedHashMap<>();for(String key:List.of("id","type","assigneeId","dueDate","plannedHours","actualHours","remainingHours","iterationId","parentId","priorityId","severity"))row.put(key,item.get(key));
            row.put("projectId",project);row.put("iterationId",iteration);row.put("status",status.get("name"));row.put("updatedAt",item.get("updatedAt"));output.add(row);
        }
        return slice(output,page,size);
    }
    private UUID projectId(UUID id){UUID cursor=id;while(cursor!=null){var item=items.raw(cursor);if("PROJECT".equals(item.get("type")))return cursor;cursor=(UUID)item.get("parent_id");}return null;}
    private UUID reportIterationId(UUID id){var rows=db.queryForList("SELECT iteration_id FROM work_item_iteration WHERE work_item_id=? ORDER BY added_at DESC LIMIT 1",id);return rows.isEmpty()?null:(UUID)rows.getFirst().get("iteration_id");}
    private boolean iterationMatches(String expected,UUID itemId){if(expected==null||expected.isBlank())return true;UUID id=Values.uuid(expected,"iterationId");return db.queryForObject("SELECT count(*) FROM work_item_iteration WHERE work_item_id=? AND iteration_id=?",Integer.class,itemId,id)>0;}
    private boolean match(Map<String,String> f,String key,Object value){String expected=f.get(key);return expected==null||expected.isBlank()||Objects.toString(value,"").equals(expected);}
    @GetMapping("/reports/iterations") public Object reportIterations(@RequestParam Map<String,String> filters){
        access.reports();int page=page(filters.get("page"),1),size=Math.min(500,page(filters.get("pageSize"),100));
        LocalDate from=Values.date(filters.get("periodFrom"),"periodFrom"),to=Values.date(filters.get("periodTo"),"periodTo");
        List<Map<String,Object>> result=new ArrayList<>();for(var raw:db.queryForList("SELECT * FROM iteration ORDER BY start_date,id")){
            LocalDate start=((java.sql.Date)raw.get("start_date")).toLocalDate(),end=((java.sql.Date)raw.get("end_date")).toLocalDate();
            if(from!=null&&end.isBefore(from)||to!=null&&start.isAfter(to))continue;
            result.add(Map.of("id",raw.get("id"),"name",raw.get("name"),"startDate",start,"endDate",end,"state",raw.get("state"),"baseline",changes.parseMap(raw.get("baseline_snapshot")),"result",changes.parseMap(raw.get("result_snapshot"))));
        }return slice(result,page,size);
    }
    @GetMapping("/reports/time-logs") public Object reportTimeLogs(@RequestParam Map<String,String> filters){
        access.reports();int page=page(filters.get("page"),1),size=Math.min(500,page(filters.get("pageSize"),100));
        LocalDate from=Values.date(filters.get("periodFrom"),"periodFrom"),to=Values.date(filters.get("periodTo"),"periodTo");
        StringBuilder sql=new StringBuilder("SELECT t.id,t.work_item_id AS \"workItemId\",t.external_user_id AS \"userId\",t.logged_date AS \"loggedDate\",t.hours FROM time_log_entry t WHERE 1=1");List<Object> args=new ArrayList<>();
        if(from!=null){sql.append(" AND t.logged_date>=?");args.add(java.sql.Date.valueOf(from));}if(to!=null){sql.append(" AND t.logged_date<=?");args.add(java.sql.Date.valueOf(to));}
        if(filters.get("assigneeId")!=null){sql.append(" AND t.external_user_id=?");args.add(filters.get("assigneeId"));}
        var rows=db.queryForList(sql+" ORDER BY t.logged_date,t.id",args.toArray());List<Map<String,Object>> output=new ArrayList<>();
        for(var row:rows){UUID itemId=(UUID)row.get("workItemId");var item=items.raw(itemId);
            if(!match(filters,"projectId",projectId(itemId))||!iterationMatches(filters.get("iterationId"),itemId)||!match(filters,"type",item.get("type")))continue;
            if(filters.get("status")!=null){String status=db.queryForObject("SELECT name FROM status WHERE id=?",String.class,item.get("status_id"));if(!filters.get("status").equals(status)&&!filters.get("status").equals(item.get("status_id").toString()))continue;}
            output.add(row);
        }
        return slice(output,page,size);
    }
    @GetMapping("/reports/statuses") public Object reportStatuses(){access.reports();return db.queryForList("SELECT id,name,board_order AS \"boardOrder\",category,active FROM status ORDER BY board_order");}
    private int page(String input,int fallback){try{int v=input==null?fallback:Integer.parseInt(input);if(v<1)throw new NumberFormatException();return v;}catch(NumberFormatException e){throw ApiException.invalid("page","invalid_integer");}}
    private Map<String,Object> slice(List<?> rows,int page,int size){int from=Math.min(rows.size(),(page-1)*size),to=Math.min(rows.size(),from+size);return Map.of("items",rows.subList(from,to),"page",page,"pageSize",size,"totalPages",(rows.size()+size-1)/size);}
}
