package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.UUID;

@RestController @RequestMapping("/api/v1/iterations")
public class IterationController {
    private final IterationService service;
    public IterationController(IterationService service){this.service=service;}
    @GetMapping public Object list(){return service.list();}
    @PostMapping public ResponseEntity<?> create(@RequestBody Map<String,Object> body){return ResponseEntity.status(201).body(service.create(body));}
    @GetMapping("/{id}") public Object view(@PathVariable UUID id){return service.view(id);}
    @PatchMapping("/{id}") public Object update(@PathVariable UUID id,@RequestBody Map<String,Object> body){return service.update(id,body);}
    @PutMapping("/{id}/capacity") public Object capacity(@PathVariable UUID id,@RequestBody Map<String,Object> body){return service.capacity(id,body);}
    @PutMapping("/{id}/items/{itemId}") public Object add(@PathVariable UUID id,@PathVariable UUID itemId){return service.add(id,itemId);}
    @DeleteMapping("/{id}/items/{itemId}") public Object remove(@PathVariable UUID id,@PathVariable UUID itemId){return service.remove(id,itemId);}
    @PostMapping("/{id}/activate") public Object activate(@PathVariable UUID id){return service.activate(id);}
    @PostMapping("/{id}/complete") public Object complete(@PathVariable UUID id){return service.complete(id);}
}
