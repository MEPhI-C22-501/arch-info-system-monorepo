package ru.mephi.arch.tasktracker;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.stereotype.Component;
import org.springframework.core.annotation.Order;
import org.springframework.core.Ordered;
import org.springframework.jdbc.core.JdbcTemplate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestControllerAdvice
public class ApiAdvice {
    private static final Logger log = LoggerFactory.getLogger(ApiAdvice.class);
    static String correlationId() { return MDC.get("correlationId") == null ? UUID.randomUUID().toString() : MDC.get("correlationId"); }
    static Map<String,Object> error(String field, String reason) {
        return Map.of("correlationId", correlationId(), "errors", List.of(Map.of("field", field, "reason", reason)));
    }
    @ExceptionHandler(ApiException.class)
    ResponseEntity<?> api(ApiException e) { return ResponseEntity.status(e.status).body(error(e.field, e.getMessage())); }
    @ExceptionHandler(DataIntegrityViolationException.class)
    ResponseEntity<?> integrity(DataIntegrityViolationException e) { return ResponseEntity.status(409).body(error("data", "constraint_violation")); }
    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<?> malformed(HttpMessageNotReadableException e) { return ResponseEntity.badRequest().body(error("body", "malformed_json")); }
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ResponseEntity<?> wrongType(MethodArgumentTypeMismatchException e) { return ResponseEntity.badRequest().body(error(e.getName(), "invalid_type")); }
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    ResponseEntity<?> tooLarge(MaxUploadSizeExceededException e) { return ResponseEntity.status(413).body(error("file", "too_large")); }
    @ExceptionHandler(Exception.class)
    ResponseEntity<?> unexpected(Exception e) {
        log.error("Request failed correlationId={}", correlationId(), e);
        return ResponseEntity.internalServerError().body(error("request", "internal_error"));
    }
}

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
class CorrelationFilter extends OncePerRequestFilter {
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
        String supplied = request.getHeader("X-Correlation-ID");
        String id = supplied != null && supplied.matches("[A-Za-z0-9._-]{1,100}") ? supplied : UUID.randomUUID().toString();
        MDC.put("correlationId", id);
        response.setHeader("X-Correlation-ID", id);
        try { chain.doFilter(request, response); } finally { MDC.remove("correlationId"); }
    }
}

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
class IntegrationRequestLogFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(IntegrationRequestLogFilter.class);
    private final JdbcTemplate db;
    IntegrationRequestLogFilter(JdbcTemplate db) { this.db = db; }
    @Override protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !path.equals("/api/v1/bugs") && !path.startsWith("/api/v1/reports/");
    }
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
        long started = System.nanoTime();
        try { chain.doFilter(request, response); }
        finally {
            try {
                db.update("INSERT INTO integration_request_log(id,occurred_at,duration_ms,correlation_id,method,path,status_code) VALUES(?,?,?,?,?,?,?)",
                    UUID.randomUUID(), OffsetDateTime.now(ZoneOffset.UTC), (System.nanoTime()-started)/1_000_000,
                    ApiAdvice.correlationId(), request.getMethod(), request.getRequestURI(), response.getStatus());
            } catch (Exception e) { log.warn("Could not persist integration request log", e); }
        }
    }
}
