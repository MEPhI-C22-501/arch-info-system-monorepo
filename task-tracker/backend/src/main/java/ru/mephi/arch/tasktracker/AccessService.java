package ru.mephi.arch.tasktracker;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

@Service
public class AccessService {
    private final JdbcTemplate db;
    private static final Set<String> HUMAN_ROLES = Set.of("MEMBER", "LEAD", "ADMIN");

    public AccessService(JdbcTemplate db) {
        this.db = db;
    }
    JwtAuthenticationToken token() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (!(auth instanceof JwtAuthenticationToken jwt)) throw new ApiException(401, "token", "unauthorized");
        return jwt;
    }
    public String subject() { return token().getToken().getSubject(); }
    private Set<String> clientRoles() {
        Object access = token().getToken().getClaims().get("resource_access");
        if (!(access instanceof Map<?, ?> clients) || !(clients.get("task-tracker") instanceof Map<?, ?> entry)
            || !(entry.get("roles") instanceof List<?> roles) || !roles.stream().allMatch(String.class::isInstance)) {
            return Set.of();
        }
        var result = new TreeSet<String>();
        for (Object role : roles) result.add((String) role);
        return result;
    }

    public boolean clientRole(String role) { return clientRoles().contains(role); }

    public void testing() { if (!clientRole("testing-service")) throw new ApiException(403,"scope","insufficient_scope"); }
    public void reports() { if (!clientRole("reports-service")) throw new ApiException(403,"scope","insufficient_scope"); }

    public Set<String> roles() {
        Set<String> roles = new TreeSet<>(clientRoles());
        roles.retainAll(HUMAN_ROLES);
        if (roles.isEmpty()) throw new ApiException(403, "access", "forbidden");
        return roles;
    }

    private boolean grants(String role, String permission) {
        return Boolean.TRUE.equals(db.query("SELECT allowed FROM role_permission WHERE role=? AND permission=?",
            rs -> rs.next() ? rs.getBoolean(1) : null, role, permission));
    }

    public boolean ownOnly(String permission) {
        return roles().stream().filter(role -> !"MEMBER".equals(role)).noneMatch(role -> grants(role, permission));
    }

    public void require(String permission) {
        if (roles().stream().noneMatch(role -> grants(role, permission))) {
            throw new ApiException(403, "permission", "forbidden");
        }
    }

    public void itemRead(Map<String,Object> item) {
        require("item.read");
        if (ownOnly("item.read") && !subject().equals(item.get("assignee_external_id"))) throw new ApiException(403,"item","forbidden");
    }
    /** QA's read-only account (Q-09): single-item + comment reads only, never list/search or
     * write — those still go through {@link #itemRead}/{@link #require} unmodified. */
    public void itemReadOrQa(Map<String,Object> item) {
        if (clientRole("qa-tracker-reader")) return;
        itemRead(item);
    }
    public void itemWrite(Map<String,Object> item) {
        require("item.update");
        if (ownOnly("item.update") && !subject().equals(item.get("assignee_external_id"))) throw new ApiException(403,"item","forbidden");
    }
}
