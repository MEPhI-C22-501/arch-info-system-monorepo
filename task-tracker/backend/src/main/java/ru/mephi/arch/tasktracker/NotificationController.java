package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

@RestController @RequestMapping("/api/v1/notifications")
public class NotificationController {
    private final JdbcTemplate db;private final AccessService access;
    public NotificationController(JdbcTemplate db,AccessService access){this.db=db;this.access=access;}
    @GetMapping public Object list(){access.require("notifications.read");return db.queryForList("SELECT id,work_item_id AS \"workItemId\",work_item_public_id AS \"workItemPublicId\",work_item_title AS \"workItemTitle\",message,actor,created_at AS \"createdAt\",read_at AS \"readAt\" FROM notification WHERE recipient_external_id=? ORDER BY created_at DESC,id DESC",access.subject());}
    @PatchMapping("/{id}") public ResponseEntity<?> markRead(@PathVariable UUID id){access.require("notifications.read");int updated=db.update("UPDATE notification SET read_at=COALESCE(read_at,?) WHERE id=? AND recipient_external_id=?",OffsetDateTime.now(ZoneOffset.UTC),id,access.subject());if(updated==0)throw ApiException.missing("notificationId");return ResponseEntity.noContent().build();}
}
