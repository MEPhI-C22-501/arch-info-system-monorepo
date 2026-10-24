package ru.mephi.arch.tasktracker.domain.workitem;

import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class WorkItemFactoryTest {
    private final OffsetDateTime now = OffsetDateTime.now();

    private WorkItem item(WorkItemType type, UUID parentId) {
        return new WorkItem(UUID.randomUUID(), type, "t", "", UUID.randomUUID(), UUID.randomUUID(), null,
            null, null, null, parentId, null, null, null, null, null, null, 0L, now, now);
    }

    @Test void epicWithoutParentIsRejected() {
        var e = assertThrows(ApiException.class, () -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.EPIC, null, null));
        assertEquals("required_for_type", e.getMessage());
    }

    @Test void subtaskWithoutParentIsRejected() {
        var e = assertThrows(ApiException.class, () -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.SUBTASK, null, null));
        assertEquals("required_for_type", e.getMessage());
    }

    @Test void projectAndTaskMayHaveNoParent() {
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.PROJECT, null, null));
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.TASK, null, null));
    }

    @Test void itemCannotBeItsOwnParent() {
        UUID id = UUID.randomUUID();
        var e = assertThrows(ApiException.class, () -> WorkItemFactory.validateParentage(id, WorkItemType.SUBTASK, id, item(WorkItemType.TASK, null)));
        assertEquals("self_parent", e.getMessage());
    }

    @Test void epicMustBeChildOfProject() {
        var badParent = item(WorkItemType.EPIC, null);
        var e = assertThrows(ApiException.class,
            () -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.EPIC, badParent.id, badParent));
        assertEquals("invalid_hierarchy", e.getMessage());
        var goodParent = item(WorkItemType.PROJECT, null);
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.EPIC, goodParent.id, goodParent));
    }

    @Test void taskAndBugMustBeChildOfEpic() {
        var epic = item(WorkItemType.EPIC, null);
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.TASK, epic.id, epic));
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.BUG, epic.id, epic));
        var project = item(WorkItemType.PROJECT, null);
        assertThrows(ApiException.class, () -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.TASK, project.id, project));
    }

    @Test void subtaskMustBeChildOfTaskOrBug() {
        var task = item(WorkItemType.TASK, null);
        var bug = item(WorkItemType.BUG, null);
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.SUBTASK, task.id, task));
        assertDoesNotThrow(() -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.SUBTASK, bug.id, bug));
    }

    @Test void projectCanNeverHaveAParent() {
        var other = item(WorkItemType.PROJECT, null);
        var e = assertThrows(ApiException.class,
            () -> WorkItemFactory.validateParentage(UUID.randomUUID(), WorkItemType.PROJECT, other.id, other));
        assertEquals("invalid_hierarchy", e.getMessage());
    }

    @Test void dueDateBeforeStartDateIsRejected() {
        var e = assertThrows(ApiException.class,
            () -> WorkItemFactory.validateDates(LocalDate.of(2026, 1, 10), LocalDate.of(2026, 1, 1)));
        assertEquals("before_start_date", e.getMessage());
        assertDoesNotThrow(() -> WorkItemFactory.validateDates(LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 10)));
        assertDoesNotThrow(() -> WorkItemFactory.validateDates(null, null));
    }

    @Test void plannedHoursCannotBeSetDirectlyOnProjectOrEpic() {
        assertThrows(ApiException.class, () -> WorkItemFactory.validatePlannedHoursAllowed(WorkItemType.PROJECT, BigDecimal.ONE));
        assertThrows(ApiException.class, () -> WorkItemFactory.validatePlannedHoursAllowed(WorkItemType.EPIC, BigDecimal.ONE));
        assertDoesNotThrow(() -> WorkItemFactory.validatePlannedHoursAllowed(WorkItemType.TASK, BigDecimal.ONE));
        assertDoesNotThrow(() -> WorkItemFactory.validatePlannedHoursAllowed(WorkItemType.PROJECT, null));
    }
}
