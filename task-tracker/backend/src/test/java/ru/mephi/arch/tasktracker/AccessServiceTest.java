package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import java.sql.ResultSet;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class AccessServiceTest {
    @AfterEach void clearAuthentication() { SecurityContextHolder.clearContext(); }

    @Test void memberCannotReadOrWriteAnotherAssigneesItem() {
        JdbcTemplate db = mock(JdbcTemplate.class);
        ResultSet row = mock(ResultSet.class);
        try {
            when(row.next()).thenReturn(true);
            when(row.getBoolean(1)).thenReturn(true);
        } catch (java.sql.SQLException e) { throw new AssertionError(e); }
        when(db.queryForList("SELECT role, allowed FROM local_access WHERE external_user_id=?", "member"))
            .thenReturn(java.util.List.of(Map.of("role", "MEMBER", "allowed", true)));
        doAnswer(call -> ((org.springframework.jdbc.core.ResultSetExtractor<?>) call.getArgument(1)).extractData(row))
            .when(db).query(eq("SELECT allowed FROM role_permission WHERE role=? AND permission=?"),
                any(org.springframework.jdbc.core.ResultSetExtractor.class), eq("MEMBER"), anyString());
        Jwt jwt = Jwt.withTokenValue("test").header("alg", "none").subject("member").build();
        SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(jwt));
        AccessService access = new AccessService(db, "");
        var other = Map.<String,Object>of("assignee_external_id", "other");
        assertEquals(403, assertThrows(ApiException.class, () -> access.itemRead(other)).status);
        assertEquals(403, assertThrows(ApiException.class, () -> access.itemWrite(other)).status);
        assertDoesNotThrow(() -> access.itemRead(Map.of("assignee_external_id", "member")));
    }
}
