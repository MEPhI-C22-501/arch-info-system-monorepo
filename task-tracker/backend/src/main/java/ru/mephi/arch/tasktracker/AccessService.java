package ru.mephi.arch.tasktracker;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Map;

@Service
public class AccessService {
    private final JdbcTemplate db;
    private final String bootstrapAdmin;
    public AccessService(JdbcTemplate db, @Value("${app.bootstrap-admin-subject:}") String bootstrapAdmin) {
        this.db = db; this.bootstrapAdmin = bootstrapAdmin;
    }
    JwtAuthenticationToken token() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (!(auth instanceof JwtAuthenticationToken jwt)) throw new ApiException(401, "token", "unauthorized");
        return jwt;
    }
    public String subject() { return token().getToken().getSubject(); }
    @SuppressWarnings("unchecked")
    private boolean clientRole(String role) {
        Object access = token().getToken().getClaims().get("resource_access");
        if (!(access instanceof Map<?,?> clients)) return false;
        Object app = clients.get("task-tracker");
        return app instanceof Map<?,?> entry && entry.get("roles") instanceof List<?> roles && roles.contains(role);
    }
    public void testing() { if (!clientRole("testing-service")) throw new ApiException(403,"scope","insufficient_scope"); }
    public void reports() { if (!clientRole("reports-service")) throw new ApiException(403,"scope","insufficient_scope"); }
    public String role() {
        if (clientRole("testing-service") || clientRole("reports-service")) throw new ApiException(403,"scope","service_client_only");
        if (!bootstrapAdmin.isBlank() && bootstrapAdmin.equals(subject())) return "ADMIN";
        var rows = db.queryForList("SELECT role, allowed FROM local_access WHERE external_user_id=?", subject());
        if (rows.isEmpty() || !Boolean.TRUE.equals(rows.getFirst().get("allowed"))) throw new ApiException(403,"access","local_access_denied");
        return (String) rows.getFirst().get("role");
    }
    public void require(String permission) {
        String role = role();
        Boolean allowed = db.query("SELECT allowed FROM role_permission WHERE role=? AND permission=?", rs -> rs.next() ? rs.getBoolean(1) : null, role, permission);
        if (!Boolean.TRUE.equals(allowed)) throw new ApiException(403,"permission","forbidden");
    }
    public void itemRead(Map<String,Object> item) {
        require("item.read");
        if (role().equals("MEMBER") && !subject().equals(item.get("assignee_external_id"))) throw new ApiException(403,"item","forbidden");
    }
    public void itemWrite(Map<String,Object> item) {
        require("item.update");
        if (role().equals("MEMBER") && !subject().equals(item.get("assignee_external_id"))) throw new ApiException(403,"item","forbidden");
    }
}
