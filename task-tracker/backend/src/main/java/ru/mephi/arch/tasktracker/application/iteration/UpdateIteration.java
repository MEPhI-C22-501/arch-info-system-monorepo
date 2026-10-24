package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;

import java.time.LocalDate;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
public class UpdateIteration {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    private final ViewIteration view;
    public UpdateIteration(IterationRepository iterations, PermissionPort permissions, ViewIteration view) {
        this.iterations = iterations; this.permissions = permissions; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID id, Map<String, Object> body) {
        permissions.require("iteration.write");
        var iteration = iterations.getById(id);
        iteration.ensureEditable();
        String name = Objects.toString(body.getOrDefault("name", iteration.name), "").trim();
        if (name.isEmpty()) throw ApiException.invalid("name", "required");
        LocalDate start = Values.date(body.getOrDefault("startDate", iteration.startDate), "startDate");
        LocalDate end = Values.date(body.getOrDefault("endDate", iteration.endDate), "endDate");
        if (start == null || end == null || end.isBefore(start)) throw ApiException.invalid("dates", "invalid_range");
        iteration.name = name;
        iteration.description = Objects.toString(body.getOrDefault("description", iteration.description), "");
        iteration.startDate = start; iteration.endDate = end;
        iterations.update(iteration);
        return view.execute(id);
    }
}
