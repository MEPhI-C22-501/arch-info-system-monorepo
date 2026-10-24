package ru.mephi.arch.tasktracker;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import ru.mephi.arch.tasktracker.application.iteration.*;

import java.util.Map;
import java.util.UUID;

@RestController @RequestMapping("/api/v1/iterations")
public class IterationController {
    private final ListIterations listIterations;
    private final CreateIteration createIteration;
    private final ViewIteration viewIteration;
    private final UpdateIteration updateIteration;
    private final SetCapacity setCapacity;
    private final AddWorkItemToIteration addWorkItemToIteration;
    private final RemoveWorkItemFromIteration removeWorkItemFromIteration;
    private final ActivateIteration activateIteration;
    private final CompleteIteration completeIteration;

    public IterationController(ListIterations listIterations, CreateIteration createIteration, ViewIteration viewIteration,
                                UpdateIteration updateIteration, SetCapacity setCapacity, AddWorkItemToIteration addWorkItemToIteration,
                                RemoveWorkItemFromIteration removeWorkItemFromIteration, ActivateIteration activateIteration,
                                CompleteIteration completeIteration) {
        this.listIterations = listIterations; this.createIteration = createIteration; this.viewIteration = viewIteration;
        this.updateIteration = updateIteration; this.setCapacity = setCapacity; this.addWorkItemToIteration = addWorkItemToIteration;
        this.removeWorkItemFromIteration = removeWorkItemFromIteration; this.activateIteration = activateIteration;
        this.completeIteration = completeIteration;
    }

    @GetMapping public Object list() { return listIterations.execute(); }
    @PostMapping public ResponseEntity<?> create(@RequestBody Map<String, Object> body) { return ResponseEntity.status(201).body(createIteration.execute(body)); }
    @GetMapping("/{id}") public Object view(@PathVariable UUID id) { return viewIteration.execute(id); }
    @PatchMapping("/{id}") public Object update(@PathVariable UUID id, @RequestBody Map<String, Object> body) { return updateIteration.execute(id, body); }
    @PutMapping("/{id}/capacity") public Object capacity(@PathVariable UUID id, @RequestBody Map<String, Object> body) { return setCapacity.execute(id, body); }
    @PutMapping("/{id}/items/{itemId}") public Object add(@PathVariable UUID id, @PathVariable UUID itemId) { return addWorkItemToIteration.execute(id, itemId); }
    @DeleteMapping("/{id}/items/{itemId}") public Object remove(@PathVariable UUID id, @PathVariable UUID itemId) { return removeWorkItemFromIteration.execute(id, itemId); }
    @PostMapping("/{id}/activate") public Object activate(@PathVariable UUID id) { return activateIteration.execute(id); }
    @PostMapping("/{id}/complete") public Object complete(@PathVariable UUID id) { return completeIteration.execute(id); }
}
