package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.domain.event.IterationActivated;
import ru.mephi.arch.tasktracker.domain.iteration.IterationState;

import java.util.Map;
import java.util.UUID;

@Service
public class ActivateIteration {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    private final IterationMetricsCalculator metrics;
    private final EventPublisherPort events;
    private final ViewIteration view;
    public ActivateIteration(IterationRepository iterations, PermissionPort permissions, IterationMetricsCalculator metrics,
                              EventPublisherPort events, ViewIteration view) {
        this.iterations = iterations; this.permissions = permissions; this.metrics = metrics;
        this.events = events; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID id) {
        permissions.require("iteration.write");
        var iteration = iterations.getById(id);
        if (iteration.state != IterationState.PLANNED) throw ApiException.conflict("state", "not_planned");
        Map<String, Object> snapshot = metrics.compute(id);
        iterations.activate(id, snapshot);
        events.publish(new IterationActivated(id, permissions.currentSubject()));
        return view.execute(id);
    }
}
