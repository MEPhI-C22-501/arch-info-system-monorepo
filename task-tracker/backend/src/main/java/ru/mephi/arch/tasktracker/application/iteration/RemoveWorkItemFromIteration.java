package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.event.IterationCompositionChanged;

import java.util.Map;
import java.util.UUID;

@Service
public class RemoveWorkItemFromIteration {
    private final IterationRepository iterations;
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final EventPublisherPort events;
    private final ViewIteration view;
    public RemoveWorkItemFromIteration(IterationRepository iterations, WorkItemRepository workItems, PermissionPort permissions,
                                        EventPublisherPort events, ViewIteration view) {
        this.iterations = iterations; this.workItems = workItems; this.permissions = permissions;
        this.events = events; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID iterationId, UUID workItemId) {
        permissions.require("iteration.write");
        var iteration = iterations.getById(iterationId);
        iteration.ensureEditable();
        if (!iterations.removeMember(iterationId, workItemId)) throw ApiException.missing("membership");
        workItems.touch(workItemId);
        String actor = permissions.currentSubject();
        events.publish(new IterationCompositionChanged(workItemId, actor, null, Map.of("iterationId", iterationId.toString()),
            Map.of("iterationId", ""), "Исключён из итерации"));
        return view.execute(iterationId);
    }
}
