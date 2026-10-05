package ru.mephi.arch.tasktracker;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Service
public class AdminService {
    private final JdbcTemplate db;private final AccessService access;
    public AdminService(JdbcTemplate db,AccessService access){this.db=db;this.access=access;}
    public List<Map<String,Object>> statuses(){access.role();return db.queryForList("SELECT id,name,board_order AS \"boardOrder\",active,board_visible AS \"boardVisible\",category FROM status ORDER BY board_order,name");}
    public List<Map<String,Object>> priorities(){access.role();return db.queryForList("SELECT id,name,sort_order AS \"sortOrder\",active,code FROM priority ORDER BY sort_order,name");}
    public List<Map<String,Object>> types(){access.role();return db.queryForList("SELECT type,enabled FROM type_setting ORDER BY type");}
    public List<Map<String,Object>> users(){access.role();return db.queryForList("SELECT external_user_id AS \"id\",display_name AS \"name\",team_external_id AS \"teamId\",department_external_id AS \"departmentId\",active FROM user_cache ORDER BY display_name");}
    public List<Map<String,Object>> accessRows(){access.require("access.admin");return db.queryForList("SELECT external_user_id AS \"userId\",role,allowed FROM local_access ORDER BY external_user_id");}
    public List<Map<String,Object>> permissions(){access.require("access.admin");return db.queryForList("SELECT role,permission,allowed FROM role_permission ORDER BY role,permission");}
    public List<String> grantedPermissions(){return db.queryForList("SELECT permission FROM role_permission WHERE role=? AND allowed=true ORDER BY permission",String.class,access.role());}
    public List<Map<String,Object>> severityMapping(){access.require("priority.admin");return db.queryForList("SELECT severity,priority_id AS \"priorityId\" FROM severity_priority ORDER BY severity");}
    @Transactional public void mapSeverity(String severity,UUID priorityId){
        access.require("priority.admin");if(!Set.of("critical","high","medium","low").contains(severity))throw ApiException.invalid("severity","invalid");
        if(db.queryForObject("SELECT count(*) FROM priority WHERE id=? AND active=true",Integer.class,priorityId)==0)throw ApiException.invalid("priorityId","unknown_or_inactive");
        db.update("INSERT INTO severity_priority(severity,priority_id) VALUES(?,?) ON CONFLICT(severity) DO UPDATE SET priority_id=EXCLUDED.priority_id",severity,priorityId);
    }
    @Transactional public Map<String,Object> createStatus(Map<String,Object> body){
        access.require("status.admin");UUID id=UUID.randomUUID();String name=Values.str(body,"name",true);int order=integer(body,"boardOrder",100);
        String category=category(body.getOrDefault("category","OPEN"));boolean visible=bool(body,"boardVisible",true);
        db.update("INSERT INTO status(id,name,board_order,active,board_visible,category) VALUES(?,?,?,?,?,?)",id,name,order,true,visible,category);return status(id);
    }
    public Map<String,Object> status(UUID id){var rows=db.queryForList("SELECT id,name,board_order AS \"boardOrder\",active,board_visible AS \"boardVisible\",category FROM status WHERE id=?",id);if(rows.isEmpty())throw ApiException.missing("statusId");return rows.getFirst();}
    @Transactional public Map<String,Object> updateStatus(UUID id,Map<String,Object> body){
        access.require("status.admin");var old=status(id);String name=Objects.toString(body.getOrDefault("name",old.get("name")),"").trim();if(name.isEmpty())throw ApiException.invalid("name","required");
        int order=integer(body,"boardOrder",((Number)old.get("boardOrder")).intValue());String category=category(body.getOrDefault("category",old.get("category")));
        boolean active=bool(body,"active",(Boolean)old.get("active")),visible=bool(body,"boardVisible",(Boolean)old.get("boardVisible"));
        if((!active||!"OPEN".equals(category)) && db.queryForObject("SELECT count(*) FROM status WHERE active=true AND category='OPEN' AND id<>?",Integer.class,id)==0 && "OPEN".equals(old.get("category")))throw ApiException.conflict("status","last_open_status");
        db.update("UPDATE status SET name=?,board_order=?,active=?,board_visible=?,category=? WHERE id=?",name,order,active,visible,category,id);return status(id);
    }
    public Map<String,Object> priority(UUID id){var rows=db.queryForList("SELECT id,name,sort_order AS \"sortOrder\",active,code FROM priority WHERE id=?",id);if(rows.isEmpty())throw ApiException.missing("priorityId");return rows.getFirst();}
    @Transactional public Map<String,Object> createPriority(Map<String,Object> body){access.require("priority.admin");UUID id=UUID.randomUUID();db.update("INSERT INTO priority(id,name,sort_order,active) VALUES(?,?,?,true)",id,Values.str(body,"name",true),integer(body,"sortOrder",100));return priority(id);}
    @Transactional public Map<String,Object> updatePriority(UUID id,Map<String,Object> body){access.require("priority.admin");var old=priority(id);String name=Objects.toString(body.getOrDefault("name",old.get("name")),"").trim();if(name.isEmpty())throw ApiException.invalid("name","required");
        boolean active=bool(body,"active",(Boolean)old.get("active"));if(!active&&db.queryForObject("SELECT count(*) FROM priority WHERE active=true AND id<>?",Integer.class,id)==0)throw ApiException.conflict("priority","last_active_priority");
        db.update("UPDATE priority SET name=?,sort_order=?,active=? WHERE id=?",name,integer(body,"sortOrder",((Number)old.get("sortOrder")).intValue()),active,id);return priority(id);}
    @Transactional public void type(String type,Map<String,Object> body){access.require("type.admin");Values.type(type);db.update("UPDATE type_setting SET enabled=? WHERE type=?",bool(body,"enabled",true),type);}
    @Transactional public void localAccess(String userId,Map<String,Object> body){access.require("access.admin");
        String role=Values.str(body,"role",true);if(!Set.of("MEMBER","LEAD","ADMIN").contains(role))throw ApiException.invalid("role","invalid_role");
        if(db.queryForObject("SELECT count(*) FROM user_cache WHERE external_user_id=?",Integer.class,userId)==0)throw ApiException.invalid("userId","unknown_user");
        db.update("INSERT INTO local_access(external_user_id,role,allowed) VALUES(?,?,?) ON CONFLICT(external_user_id) DO UPDATE SET role=EXCLUDED.role,allowed=EXCLUDED.allowed",userId,role,bool(body,"allowed",true));
    }
    @Transactional public void permission(String role,String permission,Map<String,Object> body){access.require("access.admin");
        if(!Set.of("MEMBER","LEAD","ADMIN").contains(role)||!permission.matches("[a-z]+\\.[a-z]+"))throw ApiException.invalid("permission","invalid");
        boolean allowed=bool(body,"allowed",false);
        if("ADMIN".equals(role)&&"access.admin".equals(permission)&&!allowed)throw ApiException.conflict("permission","cannot_disable_admin_access");
        db.update("INSERT INTO role_permission(role,permission,allowed) VALUES(?,?,?) ON CONFLICT(role,permission) DO UPDATE SET allowed=EXCLUDED.allowed",role,permission,allowed);
    }
    private static int integer(Map<String,Object> body,String field,int fallback){Object value=body.get(field);if(value==null)return fallback;try{return Integer.parseInt(value.toString());}catch(NumberFormatException e){throw ApiException.invalid(field,"invalid_integer");}}
    private static boolean bool(Map<String,Object> body,String field,boolean fallback){Object value=body.get(field);if(value==null)return fallback;if(value instanceof Boolean b)return b;throw ApiException.invalid(field,"invalid_boolean");}
    private static String category(Object value){String s=Objects.toString(value,"");if(!Set.of("OPEN","COMPLETED","ARCHIVED").contains(s))throw ApiException.invalid("category","invalid");return s;}
}
