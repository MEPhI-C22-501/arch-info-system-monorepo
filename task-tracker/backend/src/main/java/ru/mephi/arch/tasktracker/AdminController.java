package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.UUID;

@RestController @RequestMapping("/api/v1")
public class AdminController {
    private final AdminService admin;private final AccessService access;private final DirectoryService directory;
    public AdminController(AdminService admin,AccessService access,DirectoryService directory){this.admin=admin;this.access=access;this.directory=directory;}
    @GetMapping("/me") public Object me(){return Map.of("userId",access.subject(),"role",access.role(),"permissions",admin.grantedPermissions());}
    @GetMapping("/statuses") public Object statuses(){return admin.statuses();}
    @GetMapping("/priorities") public Object priorities(){return admin.priorities();}
    @GetMapping("/types") public Object types(){return admin.types();}
    @GetMapping("/users") public Object users(){return admin.users();}
    @GetMapping("/admin/access") public Object accessRows(){return admin.accessRows();}
    @GetMapping("/admin/permissions") public Object permissions(){return admin.permissions();}
    @GetMapping("/admin/severity-mapping") public Object severityMapping(){return admin.severityMapping();}
    @PutMapping("/admin/severity-mapping/{severity}") public ResponseEntity<?> severityMapping(@PathVariable String severity,@RequestBody Map<String,Object> body){admin.mapSeverity(severity,Values.requiredUuid(body,"priorityId"));return ResponseEntity.noContent().build();}
    @PostMapping("/admin/statuses") public ResponseEntity<?> createStatus(@RequestBody Map<String,Object> body){return ResponseEntity.status(201).body(admin.createStatus(body));}
    @PatchMapping("/admin/statuses/{id}") public Object updateStatus(@PathVariable UUID id,@RequestBody Map<String,Object> body){return admin.updateStatus(id,body);}
    @PostMapping("/admin/priorities") public ResponseEntity<?> createPriority(@RequestBody Map<String,Object> body){return ResponseEntity.status(201).body(admin.createPriority(body));}
    @PatchMapping("/admin/priorities/{id}") public Object updatePriority(@PathVariable UUID id,@RequestBody Map<String,Object> body){return admin.updatePriority(id,body);}
    @PatchMapping("/admin/types/{type}") public ResponseEntity<?> type(@PathVariable String type,@RequestBody Map<String,Object> body){admin.type(type,body);return ResponseEntity.noContent().build();}
    @PutMapping("/admin/access/{userId}") public ResponseEntity<?> localAccess(@PathVariable String userId,@RequestBody Map<String,Object> body){admin.localAccess(userId,body);return ResponseEntity.noContent().build();}
    @PutMapping("/admin/permissions/{role}/{permission}") public ResponseEntity<?> permission(@PathVariable String role,@PathVariable String permission,@RequestBody Map<String,Object> body){admin.permission(role,permission,body);return ResponseEntity.noContent().build();}
    @GetMapping("/admin/directory") public Object directory(){access.require("directory.admin");return directory.status();}
    @PostMapping("/admin/directory/sync") public Object sync(){access.require("directory.admin");return directory.sync();}
}
