package ru.mephi.arch.tasktracker.application.iteration;

import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.application.workitem.ViewWorkItem;
import ru.mephi.arch.tasktracker.domain.collaboration.TimeLogEntry;
import ru.mephi.arch.tasktracker.domain.iteration.*;
import ru.mephi.arch.tasktracker.domain.workitem.*;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class IterationMetricsCalculatorTest {
    @Test void factsBelongToTheirAuthorsAndSurviveDecompositionWithoutDoubleCounting() {
        var iterations = mock(IterationRepository.class);
        var items = mock(WorkItemRepository.class);
        var logs = mock(TimeLogRepository.class);
        var statuses = mock(StatusRepository.class);
        var views = mock(ViewWorkItem.class);
        UUID iteration = UUID.randomUUID(), parent = UUID.randomUUID(), child = UUID.randomUUID(), status = UUID.randomUUID();
        LocalDate day = LocalDate.of(2026, 11, 22);
        when(iterations.getById(iteration)).thenReturn(new Iteration(iteration, "Sprint", "", day, day, IterationState.ACTIVE, OffsetDateTime.now()));
        when(iterations.findActiveMemberIds(iteration)).thenReturn(List.of(parent, child));
        when(iterations.findCapacity(iteration)).thenReturn(List.of());
        when(views.execute(parent)).thenReturn(Map.of("id", parent, "statusId", status));
        when(views.execute(child)).thenReturn(Map.of("id", child, "statusId", status));
        when(statuses.findSummary(status)).thenReturn(new StatusRepository.StatusSummary("Open", "OPEN"));
        when(items.findLeafDescendantIds(parent)).thenReturn(List.of(child));
        when(items.findLeafDescendantIds(child)).thenReturn(List.of(child));
        when(items.findDescendantIds(parent)).thenReturn(List.of(parent, child));
        when(items.findDescendantIds(child)).thenReturn(List.of(child));
        when(items.getById(child)).thenReturn(new WorkItem(child, WorkItemType.SUBTASK, "Child", "", status, status, "current-assignee",
            null, null, new BigDecimal("8"), parent, null, null, null, null, null, null, 0, OffsetDateTime.now(), OffsetDateTime.now()));
        when(logs.findByWorkItem(parent)).thenReturn(List.of(new TimeLogEntry(UUID.randomUUID(), parent, "original-author", day, new BigDecimal("3"), "", OffsetDateTime.now())));
        when(logs.findByWorkItem(child)).thenReturn(List.of(new TimeLogEntry(UUID.randomUUID(), child, "other-author", day, new BigDecimal("2"), "", OffsetDateTime.now())));
        var calculator = new IterationMetricsCalculator(iterations, items, logs, statuses, views);
        var result = calculator.compute(iteration);
        assertEquals(result, calculator.compute(iteration));
        assertEquals(new BigDecimal("8"), result.get("plannedHours"));
        assertEquals(new BigDecimal("5"), result.get("actualHours"));
        var capacity = (List<?>) result.get("capacity");
        assertTrue(capacity.stream().anyMatch(row -> row instanceof Map<?, ?> r && "original-author".equals(r.get("userId")) && new BigDecimal("3").equals(r.get("actualHours"))));
        assertTrue(capacity.stream().anyMatch(row -> row instanceof Map<?, ?> r && "current-assignee".equals(r.get("userId")) && BigDecimal.ZERO.equals(r.get("actualHours"))));
    }
}
