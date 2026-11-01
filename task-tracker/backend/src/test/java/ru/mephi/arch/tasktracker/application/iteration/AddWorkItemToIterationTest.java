package ru.mephi.arch.tasktracker.application.iteration;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.iteration.support.InMemoryIterationRepository;
import ru.mephi.arch.tasktracker.application.port.TimeLogRepository;
import ru.mephi.arch.tasktracker.application.workitem.ViewWorkItem;
import ru.mephi.arch.tasktracker.application.workitem.support.FakePermissionPort;
import ru.mephi.arch.tasktracker.application.workitem.support.FixedReferenceData;
import ru.mephi.arch.tasktracker.application.workitem.support.InMemoryWorkItemRepository;
import ru.mephi.arch.tasktracker.application.workitem.support.RecordingEventPublisher;
import ru.mephi.arch.tasktracker.domain.event.IterationCompositionChanged;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;
import ru.mephi.arch.tasktracker.domain.iteration.IterationState;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class AddWorkItemToIterationTest {
    private final InMemoryWorkItemRepository workItems = new InMemoryWorkItemRepository();
    private final InMemoryIterationRepository iterations = new InMemoryIterationRepository();
    private final FakePermissionPort permissions = new FakePermissionPort();
    private final RecordingEventPublisher events = new RecordingEventPublisher();
    private final TimeLogRepository noTimeLogs = new TimeLogRepository() {
        @Override public List<ru.mephi.arch.tasktracker.domain.collaboration.TimeLogEntry> findByWorkItem(UUID id) { return List.of(); }
        @Override public void insert(ru.mephi.arch.tasktracker.domain.collaboration.TimeLogEntry entry) { }
        @Override public BigDecimal sumHoursForWorkItem(UUID id) { return BigDecimal.ZERO; }
    };
    private final ViewWorkItem viewWorkItem = new ViewWorkItem(workItems);
    private final IterationMetricsCalculator metrics = new IterationMetricsCalculator(iterations, workItems, noTimeLogs, FixedReferenceData.statuses(), viewWorkItem);
    private final ViewIteration viewIteration = new ViewIteration(iterations, permissions, metrics);
    private final AddWorkItemToIteration addWorkItemToIteration = new AddWorkItemToIteration(iterations, workItems, permissions, events, viewIteration);

    private UUID iterationA;
    private UUID iterationB;
    private UUID itemId;

    @BeforeEach void seed() {
        permissions.role = "LEAD";
        permissions.granted = java.util.Set.of("iteration.write", "iteration.read");
        iterationA = UUID.randomUUID();
        iterationB = UUID.randomUUID();
        iterations.insert(new Iteration(iterationA, "Sprint A", "", LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 14), IterationState.PLANNED, OffsetDateTime.now()));
        iterations.insert(new Iteration(iterationB, "Sprint B", "", LocalDate.of(2026, 1, 15), LocalDate.of(2026, 1, 28), IterationState.PLANNED, OffsetDateTime.now()));
        itemId = UUID.randomUUID();
        workItems.insert(new WorkItem(itemId, WorkItemType.TASK, "Task", "", FixedReferenceData.DEFAULT_STATUS,
            FixedReferenceData.DEFAULT_PRIORITY, null, null, null, null, null, null, null, null, null, null, null,
            0L, OffsetDateTime.now(), OffsetDateTime.now()));
    }

    @Test void addingToASecondUnfinishedIterationIsRejected() {
        addWorkItemToIteration.execute(iterationA, itemId);
        var e = assertThrows(ApiException.class, () -> addWorkItemToIteration.execute(iterationB, itemId));
        assertEquals("already_in_unfinished_iteration", e.getMessage());
    }

    @Test void addingTheSameItemTwiceToTheSameIterationIsANoOp() {
        addWorkItemToIteration.execute(iterationA, itemId);
        assertDoesNotThrow(() -> addWorkItemToIteration.execute(iterationA, itemId));
        assertEquals(1, events.ofType(IterationCompositionChanged.class).size());
    }

    @Test void reAddingToADifferentIterationIsAllowedOnceTheFirstOneCompletes() {
        addWorkItemToIteration.execute(iterationA, itemId);
        iterations.getById(iterationA).state = IterationState.COMPLETED;
        assertDoesNotThrow(() -> addWorkItemToIteration.execute(iterationB, itemId));
    }

    @Test void addingRaisesIterationCompositionChangedAgainstTheWorkItemNotTheIteration() {
        addWorkItemToIteration.execute(iterationA, itemId);
        var changed = events.ofType(IterationCompositionChanged.class);
        assertEquals(1, changed.size());
        assertEquals(itemId, changed.getFirst().workItemId());
    }
}
