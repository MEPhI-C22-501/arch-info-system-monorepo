package ru.mephi.arch.tasktracker;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.*;

@Service
public class CollaborationService {
    private final JdbcTemplate db; private final AccessService access; private final WorkItemService items; private final ChangeRecorder changes; private final long maxBytes;
    public CollaborationService(JdbcTemplate db,AccessService access,WorkItemService items,ChangeRecorder changes,@Value("${app.attachment-max-bytes}") long maxBytes){
        this.db=db;this.access=access;this.items=items;this.changes=changes;this.maxBytes=maxBytes;
    }
    private void read(UUID id){access.itemRead(items.raw(id));}
    public List<Map<String,Object>> comments(UUID id){read(id);return db.queryForList("SELECT id,author_external_id AS \"authorId\",body,created_at AS \"createdAt\" FROM comment WHERE work_item_id=? ORDER BY created_at,id",id);}
    @Transactional public Map<String,Object> comment(UUID id,Map<String,Object> body){
        read(id);access.require("comment.create");String text=Values.str(body,"body",true);UUID cid=UUID.randomUUID();var now=OffsetDateTime.now(ZoneOffset.UTC);
        db.update("INSERT INTO comment(id,work_item_id,author_external_id,body,created_at) VALUES(?,?,?,?,?)",cid,id,access.subject(),text,now);
        items.touch(id);changes.record(id,access.subject(),null,Map.of("commentAdded",false),Map.of("commentAdded",cid.toString()),"Добавлен комментарий");
        return Map.of("id",cid,"body",text,"authorId",access.subject(),"createdAt",now);
    }
    private Map<String,Object> commentRaw(UUID id,UUID cid){var rows=db.queryForList("SELECT * FROM comment WHERE id=? AND work_item_id=?",cid,id);if(rows.isEmpty())throw ApiException.missing("commentId");return rows.getFirst();}
    private void canManageComment(Map<String,Object> comment){
        if(!access.subject().equals(comment.get("author_external_id")))access.require("comment.manage");
    }
    @Transactional public Map<String,Object> editComment(UUID id,UUID cid,Map<String,Object> body){
        read(id);var original=commentRaw(id,cid);canManageComment(original);String text=Values.str(body,"body",true);
        if(!text.equals(original.get("body"))){db.update("UPDATE comment SET body=? WHERE id=?",text,cid);items.touch(id);changes.record(id,access.subject(),null,Map.of("comment",original.get("body")),Map.of("comment",text),"Изменён комментарий");}
        return Map.of("id",cid,"body",text,"authorId",original.get("author_external_id"),"createdAt",original.get("created_at"));
    }
    @Transactional public void deleteComment(UUID id,UUID cid){
        read(id);var original=commentRaw(id,cid);canManageComment(original);db.update("DELETE FROM comment WHERE id=?",cid);
        items.touch(id);changes.record(id,access.subject(),null,Map.of("commentRemoved",false),Map.of("commentRemoved",cid.toString()),"Удалён комментарий");
    }
    public List<Map<String,Object>> timeLogs(UUID id){read(id);return db.queryForList("SELECT id,external_user_id AS \"userId\",logged_date AS \"loggedDate\",hours,comment,created_at AS \"createdAt\" FROM time_log_entry WHERE work_item_id=? ORDER BY logged_date,created_at",id);}
    @Transactional public Map<String,Object> timeLog(UUID id,Map<String,Object> body){
        read(id);access.require("time.create");
        if(db.queryForObject("SELECT count(*) FROM work_item WHERE parent_id=?",Integer.class,id)>0 || Set.of("PROJECT","EPIC").contains(items.raw(id).get("type"))) throw ApiException.invalid("workItemId","time_only_for_leaf");
        BigDecimal hours=Values.hours(body.get("hours"),"hours",true);if(hours==null)throw ApiException.invalid("hours","required");
        LocalDate date=Values.date(body.get("loggedDate"),"loggedDate");if(date==null)throw ApiException.invalid("loggedDate","required");
        UUID logId=UUID.randomUUID();String note=Objects.toString(body.get("comment"),"");var now=OffsetDateTime.now(ZoneOffset.UTC);
        db.update("INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,comment,created_at) VALUES(?,?,?,?,?,?,?)",logId,id,access.subject(),java.sql.Date.valueOf(date),hours,note,now);
        items.touch(id);changes.record(id,access.subject(),null,Map.of("timeLogAdded",false),Map.of("timeLogAdded",logId.toString()),"Зарегистрировано время");
        return Map.of("id",logId,"hours",hours,"loggedDate",date,"comment",note,"userId",access.subject());
    }
    public List<Map<String,Object>> attachments(UUID id){read(id);return db.queryForList("SELECT id,file_name AS \"fileName\",size_bytes AS \"sizeBytes\",content_type AS \"contentType\",uploaded_by_external_id AS \"uploadedById\",uploaded_at AS \"uploadedAt\" FROM attachment WHERE work_item_id=? ORDER BY uploaded_at",id);}
    @Transactional public Map<String,Object> attach(UUID id,MultipartFile file) throws IOException{
        read(id);access.require("attachment.create");
        if(file.isEmpty()||file.getSize()>maxBytes)throw ApiException.invalid("file","empty_or_too_large");
        UUID aid=UUID.randomUUID();String name=Optional.ofNullable(file.getOriginalFilename()).orElse("attachment").replaceAll("[\\r\\n/\\\\]","_");
        String type=Optional.ofNullable(file.getContentType()).orElse("application/octet-stream");var now=OffsetDateTime.now(ZoneOffset.UTC);
        db.update("INSERT INTO attachment(id,work_item_id,file_name,size_bytes,content_type,content,uploaded_by_external_id,uploaded_at) VALUES(?,?,?,?,?,?,?,?)",aid,id,name,file.getSize(),type,file.getBytes(),access.subject(),now);
        items.touch(id);changes.record(id,access.subject(),null,Map.of("attachmentAdded",false),Map.of("attachmentAdded",aid.toString()),"Добавлен файл");
        return Map.of("id",aid,"fileName",name,"sizeBytes",file.getSize(),"contentType",type,"uploadedById",access.subject(),"uploadedAt",now);
    }
    private Map<String,Object> attachmentRaw(UUID id,UUID aid){var rows=db.queryForList("SELECT * FROM attachment WHERE id=? AND work_item_id=?",aid,id);if(rows.isEmpty())throw ApiException.missing("attachmentId");return rows.getFirst();}
    public ResponseEntity<byte[]> download(UUID id,UUID aid){read(id);var a=attachmentRaw(id,aid);return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename*=UTF-8''"+java.net.URLEncoder.encode((String)a.get("file_name"),java.nio.charset.StandardCharsets.UTF_8)).contentType(MediaType.parseMediaType((String)a.get("content_type"))).body((byte[])a.get("content"));}
    @Transactional public void deleteAttachment(UUID id,UUID aid){
        read(id);access.require("attachment.delete");var a=attachmentRaw(id,aid);
        if("MEMBER".equals(access.role())&&!access.subject().equals(a.get("uploaded_by_external_id")))throw new ApiException(403,"attachment","forbidden");
        db.update("DELETE FROM attachment WHERE id=?",aid);items.touch(id);
        changes.record(id,access.subject(),null,Map.of("attachmentRemoved",false),Map.of("attachmentRemoved",aid.toString()),"Удалён файл");
    }
}
