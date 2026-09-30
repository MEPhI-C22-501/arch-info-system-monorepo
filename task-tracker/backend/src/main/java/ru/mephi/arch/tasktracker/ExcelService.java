package ru.mephi.arch.tasktracker;

import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.interceptor.TransactionAspectSupport;
import org.springframework.web.multipart.MultipartFile;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.*;

@Service
public class ExcelService {
    private static final List<String> COLUMNS=List.of("id","version","type","title","description","statusId","statusName","priorityId","priorityName","assigneeId","assigneeName","startDate","dueDate","plannedHours","calculatedPlannedHours","actualHours","remainingHours","parentId","iterationId");
    private final JdbcTemplate db;private final AccessService access;private final WorkItemService items;private final IterationService iterations;
    public ExcelService(JdbcTemplate db,AccessService access,WorkItemService items,IterationService iterations){this.db=db;this.access=access;this.items=items;this.iterations=iterations;}
    public byte[] export(Map<String,Object> selection) {
        access.require("excel.export");
        Set<UUID> ids=new HashSet<>();Object rawIds=selection.get("ids");
        if(rawIds instanceof List<?> list)for(Object v:list)ids.add(Values.uuid(v,"ids"));
        try(XSSFWorkbook workbook=new XSSFWorkbook();ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
            Sheet sheet=workbook.createSheet("WorkItems");Row header=sheet.createRow(0);for(int i=0;i<COLUMNS.size();i++)header.createCell(i).setCellValue(COLUMNS.get(i));
            int rowNumber=1;
            for(UUID id:db.queryForList("SELECT id FROM work_item ORDER BY created_at,id",UUID.class)){
                if(!ids.isEmpty()&&!ids.contains(id))continue;
                var raw=items.raw(id);var view=items.view(id);
                String status=db.queryForObject("SELECT name FROM status WHERE id=?",String.class,raw.get("status_id"));
                String priority=db.queryForObject("SELECT name FROM priority WHERE id=?",String.class,raw.get("priority_id"));
                String assignee=raw.get("assignee_external_id")==null?"":db.query("SELECT display_name FROM user_cache WHERE external_user_id=?",rs->rs.next()?rs.getString(1):"",raw.get("assignee_external_id"));
                Object[] cells={id,raw.get("version"),raw.get("type"),raw.get("title"),raw.get("description"),raw.get("status_id"),status,raw.get("priority_id"),priority,raw.get("assignee_external_id"),assignee,raw.get("start_date"),raw.get("due_date"),raw.get("planned_hours"),view.get("plannedHours"),view.get("actualHours"),view.get("remainingHours"),raw.get("parent_id"),view.get("iterationId")};
                Row row=sheet.createRow(rowNumber++);for(int i=0;i<cells.length;i++)row.createCell(i).setCellValue(cells[i]==null?"":cells[i].toString());
            }
            sheet.createFreezePane(0,1);workbook.write(bytes);return bytes.toByteArray();
        }catch(IOException e){throw new IllegalStateException(e);}
    }
    @Transactional public Map<String,Object> importFile(MultipartFile file) {
        access.require("excel.import");
        if(file.isEmpty())throw ApiException.invalid("file","empty");
        List<Map<String,String>> rows=new ArrayList<>();List<Map<String,Object>> errors=new ArrayList<>();
        try(Workbook workbook=WorkbookFactory.create(file.getInputStream())){
            Sheet sheet=workbook.getSheet("WorkItems");if(sheet==null)throw ApiException.invalid("file","missing_WorkItems_sheet");
            Row header=sheet.getRow(0);if(header==null||header.getLastCellNum()!=COLUMNS.size())throw ApiException.invalid("file","invalid_columns");
            DataFormatter format=new DataFormatter(Locale.ROOT);
            for(int i=0;i<COLUMNS.size();i++)if(!COLUMNS.get(i).equals(format.formatCellValue(header.getCell(i))))throw ApiException.invalid("file","invalid_columns");
            for(int r=1;r<=sheet.getLastRowNum();r++){
                Row line=sheet.getRow(r);if(line==null)continue;
                Map<String,String> row=new LinkedHashMap<>();boolean hasValue=false;
                for(int c=0;c<COLUMNS.size();c++){
                    Cell cell=line.getCell(c);if(cell!=null&&cell.getCellType()==CellType.FORMULA)errors.add(error(r+1,COLUMNS.get(c),"formula_not_allowed"));
                    String value=cell==null?"":format.formatCellValue(cell).trim();row.put(COLUMNS.get(c),value);if(!value.isBlank())hasValue=true;
                }
                if(hasValue)rows.add(row);
            }
        }catch(ApiException e){throw e;}catch(Exception e){throw ApiException.invalid("file","invalid_xlsx");}
        Set<UUID> seen=new HashSet<>();
        for(int r=0;r<rows.size();r++){
            var row=rows.get(r);int line=r+2;
            if(row.get("title").isBlank())errors.add(error(line,"title","required"));
            try{Values.type(row.get("type"));}catch(ApiException e){errors.add(error(line,"type",e.getMessage()));}
            UUID id=null;
            try{id=Values.uuid(row.get("id"),"id");if(id!=null&&!seen.add(id))errors.add(error(line,"id","duplicate_in_file"));}catch(ApiException e){errors.add(error(line,"id",e.getMessage()));}
            if(id!=null){var existing=db.queryForList("SELECT type,version FROM work_item WHERE id=?",id);if(!existing.isEmpty()){
                if(!row.get("type").equals(existing.getFirst().get("type")))errors.add(error(line,"type","immutable"));
                if(!row.get("version").equals(existing.getFirst().get("version").toString()))errors.add(error(line,"version","stale_work_item"));
            }}
            for(String key:List.of("statusId","priorityId","parentId","iterationId"))if(!row.get(key).isBlank())try{Values.uuid(row.get(key),key);}catch(ApiException e){errors.add(error(line,key,e.getMessage()));}
            for(String key:List.of("startDate","dueDate"))if(!row.get(key).isBlank())try{Values.date(row.get(key),key);}catch(ApiException e){errors.add(error(line,key,e.getMessage()));}
            if(!row.get("plannedHours").isBlank())try{Values.hours(row.get("plannedHours"),"plannedHours",false);}catch(ApiException e){errors.add(error(line,"plannedHours",e.getMessage()));}
            if(!row.get("assigneeId").isBlank()&&db.queryForObject("SELECT count(*) FROM user_cache WHERE external_user_id=?",Integer.class,row.get("assigneeId"))==0)errors.add(error(line,"assigneeId","unknown_user"));
        }
        if(!errors.isEmpty())return report(0,0,rows.size(),errors);
        rows.sort(Comparator.comparingInt(row->switch(row.get("type")){case "PROJECT"->0;case "EPIC"->1;case "TASK","BUG"->2;default->3;}));
        int created=0,updated=0;
        for(int r=0;r<rows.size();r++){
            var row=rows.get(r);UUID id=Values.uuid(row.get("id"),"id");
            Map<String,Object> input=new LinkedHashMap<>();
            for(String key:List.of("type","title","description","statusId","priorityId","assigneeId","startDate","dueDate","plannedHours","parentId"))input.put(key,row.get(key).isBlank()?null:row.get(key));
            if(id!=null)input.put("id",id);
            try{
                boolean exists=id!=null&&db.queryForObject("SELECT count(*) FROM work_item WHERE id=?",Integer.class,id)>0;
                UUID actualId;
                if(exists){input.remove("type");input.put("version",row.get("version"));items.updateAs(id,input,access.subject(),null);actualId=id;updated++;}
                else{actualId=(UUID)items.createAs(input,access.subject(),null).get("id");created++;}
                UUID iterationId=Values.uuid(row.get("iterationId"),"iterationId");
                var current=items.view(actualId).get("iterationId");
                if(current!=null&&!current.equals(iterationId))iterations.remove((UUID)current,actualId);
                if(iterationId!=null&&!iterationId.equals(current))iterations.add(iterationId,actualId);
            }catch(Exception e){TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
                String reason=e instanceof ApiException ? e.getMessage():"invalid_reference_or_constraint";
                return report(0,0,rows.size(),List.of(error(r+2,"row",reason)));
            }
        }
        return report(created,updated,0,List.of());
    }
    private Map<String,Object> error(int row,String field,String reason){return Map.of("row",row,"field",field,"reason",reason);}
    private Map<String,Object> report(int created,int updated,int rejected,List<Map<String,Object>> errors){return Map.of("created",created,"updated",updated,"rejected",rejected,"errors",errors);}
}
