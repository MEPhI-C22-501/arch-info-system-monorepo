package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;
import ru.mephi.arch.tasktracker.domain.iteration.IterationState;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
public class CreateIteration {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    private final ViewIteration view;
    public CreateIteration(IterationRepository iterations, PermissionPort permissions, ViewIteration view) {
        this.iterations = iterations; this.permissions = permissions; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(Map<String, Object> body) {
        permissions.require("iteration.write");
        String name = Values.str(body, "name", true);
        LocalDate start = Values.date(body.get("startDate"), "startDate");
        LocalDate end = Values.date(body.get("endDate"), "endDate");
        if (start == null || end == null || end.isBefore(start)) throw ApiException.invalid("dates", "invalid_range");
        UUID id = UUID.randomUUID();
        iterations.insert(new Iteration(id, name, Objects.toString(body.get("description"), ""), start, end,
            IterationState.PLANNED, OffsetDateTime.now(ZoneOffset.UTC)));
        return view.execute(id);
    }
}
