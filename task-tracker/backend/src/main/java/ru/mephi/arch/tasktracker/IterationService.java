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
public class IterationService {
    private final JdbcTemplate db;private final AccessService access;private final WorkItemService items;private final ChangeRecorder changes;
    public IterationService(JdbcTemplate db,AccessService access,WorkItemService items,ChangeRecorder changes){this.db=db;this.access=access;this.items=items;this.changes=changes;}
    private Map<String,Object> raw(UUID id){var rows=db.queryForList("SELECT * FROM iteration WHERE id=?",id);if(rows.isEmpty())throw ApiException.missing("iterationId");return rows.getFirst();}
    private void editable(UUID id){if("COMPLETED".equals(raw(id).get("state")))throw ApiException.conflict("iteration","completed");}
    private List<UUID> memberIds(UUID id){return db.queryForList("SELECT work_item_id FROM work_item_iteration WHERE iteration_id=? AND removed_at IS NULL ORDER BY added_at",UUID.class,id);}
    public List<Map<String,Object>> list(){access.require("iteration.read");return db.queryForList("SELECT id,name,description,start_date AS \"startDate\",end_date AS \"endDate\",state FROM iteration ORDER BY start_date DESC");}
    @Transactional public Map<String,Object> create(Map<String,Object> body){
        access.require("iteration.write");String name=Values.str(body,"name",true);LocalDate start=Values.date(body.get("startDate"),"startDate"),end=Values.date(body.get("endDate"),"endDate");
        if(start==null||end==null||end.isBefore(start))throw ApiException.invalid("dates","invalid_range");
        UUID id=UUID.randomUUID();db.update("INSERT INTO iteration(id,name,description,start_date,end_date,state,created_at) VALUES(?,?,?,?,?,'PLANNED',?)",id,name,Objects.toString(body.get("description"),""),Date.valueOf(start),Date.valueOf(end),OffsetDateTime.now(ZoneOffset.UTC));
        return view(id);
    }
    @Transactional public Map<String,Object> update(UUID id,Map<String,Object> body){
        access.require("iteration.write");editable(id);var current=raw(id);
        String name=Objects.toString(body.getOrDefault("name",current.get("name")),"").trim();if(name.isEmpty())throw ApiException.invalid("name","required");
        LocalDate start=Values.date(body.getOrDefault("startDate",current.get("start_date")),"startDate"),end=Values.date(body.getOrDefault("endDate",current.get("end_date")),"endDate");
        if(start==null||end==null||end.isBefore(start))throw ApiException.invalid("dates","invalid_range");
        db.update("UPDATE iteration SET name=?,description=?,start_date=?,end_date=? WHERE id=?",name,body.getOrDefault("description",current.get("description")),Date.valueOf(start),Date.valueOf(end),id);
        return view(id);
    }
    @Transactional public Map<String,Object> capacity(UUID id,Map<String,Object> body){
        access.require("capacity.write");editable(id);String user=Values.str(body,"userId",true);BigDecimal hours=Values.hours(body.get("availableHours"),"availableHours",false);
        if(hours==null)throw ApiException.invalid("availableHours","required");
        Integer found=db.queryForObject("SELECT count(*) FROM user_cache WHERE external_user_id=? AND active=true",Integer.class,user);
        if(found==0)throw ApiException.invalid("userId","unknown_or_inactive");
        db.update("INSERT INTO capacity_entry(iteration_id,external_user_id,available_hours) VALUES(?,?,?) ON CONFLICT(iteration_id,external_user_id) DO UPDATE SET available_hours=EXCLUDED.available_hours",id,user,hours);
        return view(id);
    }
    @Transactional public Map<String,Object> add(UUID id,UUID itemId){
        access.require("iteration.write");editable(id);items.raw(itemId);
        db.queryForMap("SELECT id FROM work_item WHERE id=? FOR UPDATE",itemId);
        Integer other=db.queryForObject("SELECT count(*) FROM work_item_iteration wi JOIN iteration i ON i.id=wi.iteration_id WHERE wi.work_item_id=? AND wi.removed_at IS NULL AND i.state<>'COMPLETED' AND i.id<>?",Integer.class,itemId,id);
        if(other>0)throw ApiException.conflict("iterationId","already_in_unfinished_iteration");
        Integer exists=db.queryForObject("SELECT count(*) FROM work_item_iteration WHERE iteration_id=? AND work_item_id=? AND removed_at IS NULL",Integer.class,id,itemId);
        if(exists>0)return view(id);
        db.update("INSERT INTO work_item_iteration(id,iteration_id,work_item_id,added_at) VALUES(?,?,?,?)",UUID.randomUUID(),id,itemId,OffsetDateTime.now(ZoneOffset.UTC));
        items.touch(itemId);changes.record(itemId,access.subject(),null,Map.of("iterationId",""),Map.of("iterationId",id.toString()),"Включён в итерацию");
        return view(id);
    }
    @Transactional public Map<String,Object> remove(UUID id,UUID itemId){
        access.require("iteration.write");editable(id);
        int changed=db.update("UPDATE work_item_iteration SET removed_at=? WHERE iteration_id=? AND work_item_id=? AND removed_at IS NULL",OffsetDateTime.now(ZoneOffset.UTC),id,itemId);
        if(changed==0)throw ApiException.missing("membership");
        items.touch(itemId);changes.record(itemId,access.subject(),null,Map.of("iterationId",id.toString()),Map.of("iterationId",""),"Исключён из итерации");
        return view(id);
    }
    private Map<String,Object> metrics(UUID id) {
        var selected=memberIds(id);
        Set<UUID> leafIds=new LinkedHashSet<>();
        List<Map<String,Object>> itemViews=new ArrayList<>();
        Map<String,Integer> statusCounts=new TreeMap<>();int completeCount=0;List<String> warnings=new ArrayList<>();
        LocalDate start=((Date)raw(id).get("start_date")).toLocalDate(),end=((Date)raw(id).get("end_date")).toLocalDate();
        for(UUID itemId:selected){
            var view=items.view(itemId);itemViews.add(view);
            UUID statusId=(UUID)view.get("statusId");
            var status=db.queryForMap("SELECT name,category FROM status WHERE id=?",statusId);
            statusCounts.merge((String)status.get("name"),1,Integer::sum);
            if("COMPLETED".equals(status.get("category")))completeCount++;
            if(view.get("dueDate")!=null){LocalDate due=((Date)view.get("dueDate")).toLocalDate();if(due.isBefore(start)||due.isAfter(end))warnings.add("Срок вне итерации: "+itemId);}
            var leaves=db.queryForList("WITH RECURSIVE d AS (SELECT id FROM work_item WHERE id=? UNION ALL SELECT w.id FROM work_item w JOIN d ON w.parent_id=d.id) SELECT d.id FROM d WHERE NOT EXISTS(SELECT 1 FROM work_item c WHERE c.parent_id=d.id)",UUID.class,itemId);
            leafIds.addAll(leaves);
        }
        BigDecimal planned=BigDecimal.ZERO,actual=BigDecimal.ZERO;
        Map<String,BigDecimal> load=new TreeMap<>(), spentByAssignee=new TreeMap<>();
        for(UUID leaf:leafIds){
            var item=items.raw(leaf);BigDecimal hours=(BigDecimal)item.get("planned_hours");
            if(hours==null)warnings.add("Нет оценки: "+leaf);else planned=planned.add(hours);
            String assignee=(String)item.get("assignee_external_id");
            if(assignee==null)warnings.add("Нет исполнителя: "+leaf);else load.merge(assignee,hours==null?BigDecimal.ZERO:hours,BigDecimal::add);
            BigDecimal spent=db.queryForObject("SELECT COALESCE(SUM(hours),0) FROM time_log_entry WHERE work_item_id=?",BigDecimal.class,leaf);actual=actual.add(spent);
            if(assignee!=null)spentByAssignee.merge(assignee,spent,BigDecimal::add);
        }
        List<Map<String,Object>> capacity=new ArrayList<>();BigDecimal totalCapacity=BigDecimal.ZERO;
        var capacities=db.queryForList("SELECT external_user_id,available_hours FROM capacity_entry WHERE iteration_id=? ORDER BY external_user_id",id);
        Set<String> users=new TreeSet<>(load.keySet());for(var c:capacities)users.add((String)c.get("external_user_id"));
        for(String user:users){
            BigDecimal available=capacities.stream().filter(c->user.equals(c.get("external_user_id"))).map(c->(BigDecimal)c.get("available_hours")).findFirst().orElse(BigDecimal.ZERO);
            totalCapacity=totalCapacity.add(available);BigDecimal assigned=load.getOrDefault(user,BigDecimal.ZERO);
            capacity.add(Map.of("userId",user,"availableHours",available,"plannedHours",assigned,"actualHours",spentByAssignee.getOrDefault(user,BigDecimal.ZERO),"reserveHours",available.subtract(assigned),"overloaded",assigned.compareTo(available)>0));
        }
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("items",itemViews);result.put("statusCounts",statusCounts);result.put("plannedHours",planned);result.put("actualHours",actual);result.put("remainingHours",planned.subtract(actual));
        result.put("capacity",capacity);result.put("teamCapacityHours",totalCapacity);result.put("teamReserveHours",totalCapacity.subtract(planned));
        result.put("completedCount",completeCount);result.put("completionFraction",selected.isEmpty()?0.0:(double)completeCount/selected.size());result.put("warnings",warnings);
        return result;
    }
    public Map<String,Object> view(UUID id){access.require("iteration.read");var raw=raw(id);Map<String,Object> out=new LinkedHashMap<>();
        out.put("id",id);out.put("name",raw.get("name"));out.put("description",raw.get("description"));out.put("startDate",raw.get("start_date"));out.put("endDate",raw.get("end_date"));out.put("state",raw.get("state"));
        out.putAll(metrics(id));
        Map<String,Object> baseline=changes.parseMap(raw.get("baseline_snapshot")),result=changes.parseMap(raw.get("result_snapshot"));
        if("MEMBER".equals(access.role())){
            out.put("items",visibleItems(out.get("items")));
            baseline=visibleSnapshot(baseline);
            result=visibleSnapshot(result);
        }
        out.put("baseline",baseline);out.put("result",result);return out;
    }
    private List<?> visibleItems(Object value){
        if(!(value instanceof List<?> rows))return List.of();
        return rows.stream().filter(row->row instanceof Map<?,?> item && access.subject().equals(item.get("assigneeId"))).toList();
    }
    private Map<String,Object> visibleSnapshot(Map<String,Object> input){
        Map<String,Object> output=new LinkedHashMap<>(input);
        if(output.containsKey("items"))output.put("items",visibleItems(output.get("items")));
        if(output.get("baseline") instanceof Map<?,?> baseline)output.put("baseline",visibleSnapshot(castSnapshot(baseline)));
        if(output.get("actual") instanceof Map<?,?> actual)output.put("actual",visibleSnapshot(castSnapshot(actual)));
        return output;
    }
    private Map<String,Object> castSnapshot(Map<?,?> raw){Map<String,Object> result=new LinkedHashMap<>();raw.forEach((key,value)->result.put(key.toString(),value));return result;}
    @Transactional public Map<String,Object> activate(UUID id){
        access.require("iteration.write");var current=raw(id);if(!"PLANNED".equals(current.get("state")))throw ApiException.conflict("state","not_planned");
        Map<String,Object> snapshot=metrics(id);
        db.update("UPDATE iteration SET state='ACTIVE',baseline_snapshot=CAST(? AS jsonb) WHERE id=?",changes.json(snapshot),id);
        return view(id);
    }
    @Transactional public Map<String,Object> complete(UUID id){
        access.require("iteration.write");var current=raw(id);if(!"ACTIVE".equals(current.get("state")))throw ApiException.conflict("state","not_active");
        Map<String,Object> outcome=metrics(id);Map<String,Object> baseline=changes.parseMap(current.get("baseline_snapshot"));
        Map<String,Object> comparison=new LinkedHashMap<>();comparison.put("baseline",baseline);comparison.put("actual",outcome);
        BigDecimal planned=new BigDecimal(baseline.get("plannedHours").toString());BigDecimal actual=(BigDecimal)outcome.get("actualHours");comparison.put("deviationHours",actual.subtract(planned));
        db.update("UPDATE iteration SET state='COMPLETED',result_snapshot=CAST(? AS jsonb) WHERE id=?",changes.json(comparison),id);
        return view(id);
    }
}
