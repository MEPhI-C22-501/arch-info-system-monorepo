package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.domain.event.IterationCompleted;
import ru.mephi.arch.tasktracker.domain.iteration.IterationState;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Deliberately does not touch work_item_iteration.removed_at or any item's status — "backlog" for
 * an unfinished item is a query filter on iteration.state, not a reset performed here. See
 * CLAUDE.md / the restructuring plan for why this must stay exactly this way.
 */
@Service
public class CompleteIteration {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    private final IterationMetricsCalculator metrics;
    private final EventPublisherPort events;
    private final ViewIteration view;
    public CompleteIteration(IterationRepository iterations, PermissionPort permissions, IterationMetricsCalculator metrics,
                              EventPublisherPort events, ViewIteration view) {
        this.iterations = iterations; this.permissions = permissions; this.metrics = metrics;
        this.events = events; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID id) {
        permissions.require("iteration.write");
        var iteration = iterations.getById(id);
        if (iteration.state != IterationState.ACTIVE) throw ApiException.conflict("state", "not_active");
        Map<String, Object> outcome = metrics.compute(id);
        Map<String, Object> baseline = iterations.findBaselineSnapshot(id).orElse(Map.of());
        Map<String, Object> comparison = new LinkedHashMap<>();
        comparison.put("baseline", baseline); comparison.put("actual", outcome);
        BigDecimal planned = new BigDecimal(baseline.get("plannedHours").toString());
        BigDecimal actual = (BigDecimal) outcome.get("actualHours");
        comparison.put("deviationHours", actual.subtract(planned));
        iterations.complete(id, comparison);
        events.publish(new IterationCompleted(id, permissions.currentSubject()));
        return view.execute(id);
    }
}
