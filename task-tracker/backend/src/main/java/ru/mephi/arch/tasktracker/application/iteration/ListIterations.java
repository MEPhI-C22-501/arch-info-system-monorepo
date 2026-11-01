package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;

import java.util.List;
import java.util.Map;

@Service
public class ListIterations {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    public ListIterations(IterationRepository iterations, PermissionPort permissions) {
        this.iterations = iterations; this.permissions = permissions;
    }

    public List<Map<String, Object>> execute() {
        permissions.require("iteration.read");
        return iterations.findAll().stream()
            .<Map<String, Object>>map(it -> Map.of("id", it.id, "name", it.name, "description", it.description,
                "startDate", it.startDate, "endDate", it.endDate, "state", it.state.name()))
            .toList();
    }
}
