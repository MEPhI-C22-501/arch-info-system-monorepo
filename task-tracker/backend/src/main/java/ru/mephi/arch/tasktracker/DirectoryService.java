package ru.mephi.arch.tasktracker;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.*;

@Service
public class DirectoryService {
    private final JdbcTemplate db;private final TransactionTemplate tx;private final ObjectMapper json=new ObjectMapper();
    private final String url,token;private final boolean dev;
    private final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    public DirectoryService(JdbcTemplate db,TransactionTemplate tx,@Value("${app.directory-url:}") String url,@Value("${app.directory-token:}") String token,@Value("${app.dev-directory:false}") boolean dev){
        this.db=db;this.tx=tx;this.url=url;this.token=token;this.dev=dev;
    }
    public Map<String,Object> status(){var meta=db.queryForMap("SELECT version,last_success_at AS \"lastSuccessAt\" FROM directory_meta WHERE singleton=true");
        Map<String,Object> out=new LinkedHashMap<>(meta);out.put("logs",db.queryForList("SELECT id,occurred_at AS \"occurredAt\",duration_ms AS \"durationMs\",success,correlation_id AS \"correlationId\",message FROM sync_log ORDER BY occurred_at DESC LIMIT 50"));
        out.put("teams",db.queryForList("SELECT external_id AS \"id\",display_name AS \"name\",active FROM directory_team ORDER BY display_name"));
        out.put("departments",db.queryForList("SELECT external_id AS \"id\",display_name AS \"name\",active FROM directory_department ORDER BY display_name"));return out;
    }
    @Scheduled(cron="${app.directory-cron}")
    public void scheduled(){if(!url.isBlank())try{sync();}catch(Exception ignored){/* failure is recorded in sync_log */}}
    @SuppressWarnings("unchecked")
    public Map<String,Object> sync(){
        long start=System.nanoTime();String correlation=ApiAdvice.correlationId();
        try {
            if(url.isBlank())throw new IllegalStateException("directory_url_not_configured");
            String version=Objects.toString(db.queryForObject("SELECT version FROM directory_meta WHERE singleton=true",String.class),"");
            String endpoint=url+(url.contains("?")?"&":"?")+"sinceVersion="+URLEncoder.encode(version,StandardCharsets.UTF_8);
            HttpRequest.Builder builder=HttpRequest.newBuilder(URI.create(endpoint)).timeout(Duration.ofSeconds(6)).header("Accept","application/json").header("X-Correlation-ID",correlation).GET();
            if(!token.isBlank())builder.header("Authorization","Bearer "+token);
            HttpResponse<String> response=null;
            for(int attempt=0;attempt<3;attempt++){
                try{response=http.send(builder.build(),HttpResponse.BodyHandlers.ofString());if(response.statusCode()<500)break;}
                catch(Exception e){if(attempt==2)throw e;}
                if(attempt<2)Thread.sleep(200L*(attempt+1));
            }
            if(response==null||response.statusCode()!=200)throw new IllegalStateException("directory_http_"+(response==null?"unavailable":response.statusCode()));
            Map<String,Object> snapshot=json.readValue(response.body(),Map.class);
            String nextVersion=required(snapshot,"version");
            List<Map<String,Object>> users=entries(snapshot,"users"),teams=entries(snapshot,"teams"),departments=entries(snapshot,"departments");
            tx.executeWithoutResult(s->{
                db.update("UPDATE user_cache SET active=false");db.update("UPDATE directory_team SET active=false");db.update("UPDATE directory_department SET active=false");
                for(var e:teams)db.update("INSERT INTO directory_team(external_id,display_name,active) VALUES(?,?,?) ON CONFLICT(external_id) DO UPDATE SET display_name=EXCLUDED.display_name,active=EXCLUDED.active",e.get("id"),e.get("name"),e.get("active"));
                for(var e:departments)db.update("INSERT INTO directory_department(external_id,display_name,active) VALUES(?,?,?) ON CONFLICT(external_id) DO UPDATE SET display_name=EXCLUDED.display_name,active=EXCLUDED.active",e.get("id"),e.get("name"),e.get("active"));
                for(var e:users)db.update("INSERT INTO user_cache(external_user_id,display_name,team_external_id,department_external_id,active,synced_at) VALUES(?,?,?,?,?,?) ON CONFLICT(external_user_id) DO UPDATE SET display_name=EXCLUDED.display_name,team_external_id=EXCLUDED.team_external_id,department_external_id=EXCLUDED.department_external_id,active=EXCLUDED.active,synced_at=EXCLUDED.synced_at",e.get("id"),e.get("name"),e.get("teamId"),e.get("departmentId"),e.get("active"),OffsetDateTime.now(ZoneOffset.UTC));
                db.update("UPDATE directory_meta SET version=?,last_success_at=? WHERE singleton=true",nextVersion,OffsetDateTime.now(ZoneOffset.UTC));
            });
            log(true,"synced version "+nextVersion,start,correlation);
            return Map.of("version",nextVersion,"users",users.size(),"teams",teams.size(),"departments",departments.size());
        }catch(Exception e){log(false,e.getMessage()==null?"directory_error":e.getMessage(),start,correlation);throw new ApiException(503,"directory","sync_failed");}
    }
    private String required(Map<String,Object> entry,String key){Object v=entry.get(key);if(v==null||v.toString().isBlank())throw new IllegalArgumentException("missing_"+key);return v.toString();}
    @SuppressWarnings("unchecked") private List<Map<String,Object>> entries(Map<String,Object> snapshot,String key){
        Object value=snapshot.get(key);if(!(value instanceof List<?> list))throw new IllegalArgumentException("missing_"+key);
        List<Map<String,Object>> result=new ArrayList<>();
        for(Object row:list){if(!(row instanceof Map<?,?> raw))throw new IllegalArgumentException("invalid_"+key);Map<String,Object> entry=(Map<String,Object>)raw;
            required(entry,"id");required(entry,"name");if(!(entry.get("active") instanceof Boolean))throw new IllegalArgumentException("invalid_active");result.add(entry);}
        return result;
    }
    private void log(boolean success,String message,long start,String correlation){
        db.update("INSERT INTO sync_log(id,occurred_at,duration_ms,success,correlation_id,message) VALUES(?,?,?,?,?,?)",UUID.randomUUID(),OffsetDateTime.now(ZoneOffset.UTC),(System.nanoTime()-start)/1_000_000,success,correlation,message);
    }
    @Bean ApplicationRunner devDirectorySeeder(){return args->{
        if(!dev)return;
        var now=OffsetDateTime.now(ZoneOffset.UTC);
        String[][] people={{"11111111-1111-1111-1111-111111111111","Демо участник","MEMBER"},{"22222222-2222-2222-2222-222222222222","Демо руководитель","LEAD"},{"33333333-3333-3333-3333-333333333333","Демо администратор","ADMIN"}};
        for(String[] p:people){
            db.update("INSERT INTO user_cache(external_user_id,display_name,active,synced_at) VALUES(?,?,true,?) ON CONFLICT(external_user_id) DO NOTHING",p[0],p[1],now);
            db.update("INSERT INTO local_access(external_user_id,role,allowed) VALUES(?,?,true) ON CONFLICT(external_user_id) DO NOTHING",p[0],p[2]);
        }
    };}
}
