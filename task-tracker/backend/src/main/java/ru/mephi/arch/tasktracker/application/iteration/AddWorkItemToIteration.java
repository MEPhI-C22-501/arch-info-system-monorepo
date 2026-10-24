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
public class AddWorkItemToIteration {
    private final IterationRepository iterations;
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final EventPublisherPort events;
    private final ViewIteration view;
    public AddWorkItemToIteration(IterationRepository iterations, WorkItemRepository workItems, PermissionPort permissions,
                                   EventPublisherPort events, ViewIteration view) {
        this.iterations = iterations; this.workItems = workItems; this.permissions = permissions;
        this.events = events; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID iterationId, UUID workItemId) {
        permissions.require("iteration.write");
        var iteration = iterations.getById(iterationId);
        iteration.ensureEditable();
        workItems.getById(workItemId);
        workItems.lockForUpdate(workItemId);
        if (iterations.hasOtherUnfinishedMembership(workItemId, iterationId)) {
            throw ApiException.conflict("iterationId", "already_in_unfinished_iteration");
        }
        if (iterations.isMember(iterationId, workItemId)) return view.execute(iterationId);
        iterations.addMember(iterationId, workItemId);
        workItems.touch(workItemId);
        String actor = permissions.currentSubject();
        events.publish(new IterationCompositionChanged(workItemId, actor, null, Map.of("iterationId", ""),
            Map.of("iterationId", iterationId.toString()), "Включён в итерацию"));
        return view.execute(iterationId);
    }
}
