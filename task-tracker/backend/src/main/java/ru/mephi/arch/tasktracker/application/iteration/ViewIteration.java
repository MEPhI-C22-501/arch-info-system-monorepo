package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ViewIteration {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    private final IterationMetricsCalculator metrics;
    public ViewIteration(IterationRepository iterations, PermissionPort permissions, IterationMetricsCalculator metrics) {
        this.iterations = iterations; this.permissions = permissions; this.metrics = metrics;
    }

    public Map<String, Object> execute(UUID id) {
        permissions.require("iteration.read");
        Iteration iteration = iterations.getById(id);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", id); out.put("name", iteration.name); out.put("description", iteration.description);
        out.put("startDate", iteration.startDate); out.put("endDate", iteration.endDate); out.put("state", iteration.state.name());
        out.putAll(metrics.compute(id));

        Map<String, Object> baseline = iterations.findBaselineSnapshot(id).orElse(Map.of());
        Map<String, Object> result = iterations.findResultSnapshot(id).orElse(Map.of());
        if ("MEMBER".equals(permissions.currentRole())) {
            out.put("items", visibleItems(out.get("items")));
            baseline = visibleSnapshot(baseline);
            result = visibleSnapshot(result);
        }
        out.put("baseline", baseline); out.put("result", result);
        return out;
    }

    @SuppressWarnings("unchecked")
    private List<?> visibleItems(Object value) {
        if (!(value instanceof List<?> rows)) return List.of();
        return rows.stream().filter(row -> row instanceof Map<?, ?> item && permissions.currentSubject().equals(item.get("assigneeId"))).toList();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> visibleSnapshot(Map<String, Object> input) {
        Map<String, Object> output = new LinkedHashMap<>(input);
        if (output.containsKey("items")) output.put("items", visibleItems(output.get("items")));
        if (output.get("baseline") instanceof Map<?, ?> baseline) output.put("baseline", visibleSnapshot(castSnapshot(baseline)));
        if (output.get("actual") instanceof Map<?, ?> actual) output.put("actual", visibleSnapshot(castSnapshot(actual)));
        return output;
    }

    private Map<String, Object> castSnapshot(Map<?, ?> raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        raw.forEach((key, value) -> result.put(key.toString(), value));
        return result;
    }
}
