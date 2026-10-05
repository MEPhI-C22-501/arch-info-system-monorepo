package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.net.URI;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/work-items")
public class WorkItemController {
    private final WorkItemService items;
    private final CollaborationService collaboration;
    public WorkItemController(WorkItemService items,CollaborationService collaboration){this.items=items;this.collaboration=collaboration;}
    @GetMapping public Map<String,Object> list(@RequestParam Map<String,String> filters){return items.list(filters);}
    @PostMapping public ResponseEntity<?> create(@RequestBody Map<String,Object> body){var item=items.create(body);return ResponseEntity.created(URI.create("/api/v1/work-items/"+item.get("id"))).body(item);}
    @GetMapping("/{id}") public Map<String,Object> one(@PathVariable UUID id){return items.read(id);}
    @PatchMapping("/{id}") public Map<String,Object> update(@PathVariable UUID id,@RequestBody Map<String,Object> body){return items.update(id,body);}
    @DeleteMapping("/{id}") public ResponseEntity<?> delete(@PathVariable UUID id,@RequestHeader(value="X-Confirm-Hard-Delete",required=false) String confirmation){items.delete(id,confirmation);return ResponseEntity.noContent().build();}
    @GetMapping("/{id}/history") public Object history(@PathVariable UUID id){return items.history(id);}
    @GetMapping("/{id}/comments") public Object comments(@PathVariable UUID id){return collaboration.comments(id);}
    @PostMapping("/{id}/comments") public ResponseEntity<?> comment(@PathVariable UUID id,@RequestBody Map<String,Object> body){return ResponseEntity.status(201).body(collaboration.comment(id,body));}
    @PatchMapping("/{id}/comments/{commentId}") public Object editComment(@PathVariable UUID id,@PathVariable UUID commentId,@RequestBody Map<String,Object> body){return collaboration.editComment(id,commentId,body);}
    @DeleteMapping("/{id}/comments/{commentId}") public ResponseEntity<?> deleteComment(@PathVariable UUID id,@PathVariable UUID commentId){collaboration.deleteComment(id,commentId);return ResponseEntity.noContent().build();}
    @GetMapping("/{id}/time-logs") public Object timeLogs(@PathVariable UUID id){return collaboration.timeLogs(id);}
    @PostMapping("/{id}/time-logs") public ResponseEntity<?> timeLog(@PathVariable UUID id,@RequestBody Map<String,Object> body){return ResponseEntity.status(201).body(collaboration.timeLog(id,body));}
    @GetMapping("/{id}/attachments") public Object attachments(@PathVariable UUID id){return collaboration.attachments(id);}
    @PostMapping("/{id}/attachments") public ResponseEntity<?> attach(@PathVariable UUID id,@RequestParam("file") org.springframework.web.multipart.MultipartFile file) throws java.io.IOException{return ResponseEntity.status(201).body(collaboration.attach(id,file));}
    @GetMapping("/{id}/attachments/{attachmentId}") public ResponseEntity<byte[]> download(@PathVariable UUID id,@PathVariable UUID attachmentId){return collaboration.download(id,attachmentId);}
    @DeleteMapping("/{id}/attachments/{attachmentId}") public ResponseEntity<?> deleteAttachment(@PathVariable UUID id,@PathVariable UUID attachmentId){collaboration.deleteAttachment(id,attachmentId);return ResponseEntity.noContent().build();}
}
