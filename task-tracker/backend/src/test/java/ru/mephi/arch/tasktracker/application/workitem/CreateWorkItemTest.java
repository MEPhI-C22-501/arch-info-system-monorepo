package ru.mephi.arch.tasktracker.application.workitem;

import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.workitem.support.*;
import ru.mephi.arch.tasktracker.domain.event.HierarchyChanged;
import ru.mephi.arch.tasktracker.domain.event.WorkItemCreated;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class CreateWorkItemTest {
    private final InMemoryWorkItemRepository repo = new InMemoryWorkItemRepository();
    private final FakePermissionPort permissions = new FakePermissionPort();
    private final RecordingEventPublisher events = new RecordingEventPublisher();
    private final CreateWorkItem createWorkItem = new CreateWorkItem(repo,
        FixedReferenceData.statuses(), FixedReferenceData.priorities(), FixedReferenceData.allTypesEnabled(),
        FixedReferenceData.activeUsers("member-1", "lead-1"), permissions, events, new ViewWorkItem(repo));

    @Test void memberCreatingTaskWithoutAssigneeDefaultsToSelf() {
        var input = new LinkedHashMap<String, Object>();
        input.put("type", "TASK"); input.put("title", "Do the thing");
        var result = createWorkItem.execute(input, "member-1", null);
        assertEquals("member-1", result.get("assigneeId"));
    }

    @Test void disabledTypeIsRejected() {
        var create = new CreateWorkItem(repo, FixedReferenceData.statuses(), FixedReferenceData.priorities(),
            FixedReferenceData.typesEnabledExcept(WorkItemType.BUG), FixedReferenceData.activeUsers("member-1"),
            permissions, events, new ViewWorkItem(repo));
        var input = Map.of("type", (Object) "BUG", "title", "x");
        var e = assertThrows(ApiException.class, () -> create.execute(new LinkedHashMap<>(input), "member-1", null));
        assertEquals("disabled", e.getMessage());
    }

    @Test void creatingUnderAProjectAsAnEpicClearsParentsPlannedHoursAndRaisesHierarchyChanged() {
        UUID projectId = UUID.randomUUID();
        var project = new WorkItem(projectId, WorkItemType.PROJECT, "Proj", "", FixedReferenceData.DEFAULT_STATUS,
            FixedReferenceData.DEFAULT_PRIORITY, null, null, null, null, null, null, null, null, null, null, null,
            0L, OffsetDateTime.now(), OffsetDateTime.now());
        repo.insert(project);

        var input = new LinkedHashMap<String, Object>();
        input.put("type", "EPIC"); input.put("title", "Epic 1"); input.put("parentId", projectId.toString());
        var result = createWorkItem.execute(input, "lead-1", null);

        assertEquals(1, events.ofType(WorkItemCreated.class).size());
        assertEquals(1, events.ofType(HierarchyChanged.class).size());
        assertEquals(projectId, events.ofType(HierarchyChanged.class).getFirst().workItemId());
        assertNull(repo.getById(projectId).plannedHours);
        assertNotNull(result.get("id"));
    }

    @Test void epicWithoutParentIsRejectedBeforeAnythingIsPersisted() {
        var input = new LinkedHashMap<String, Object>();
        input.put("type", "EPIC"); input.put("title", "Orphan epic");
        assertThrows(ApiException.class, () -> createWorkItem.execute(input, "lead-1", null));
        assertTrue(repo.items.isEmpty());
        assertTrue(events.published.isEmpty());
    }

    @Test void inactiveAssigneeIsRejected() {
        var input = new LinkedHashMap<String, Object>();
        input.put("type", "TASK"); input.put("title", "x"); input.put("assigneeId", "ghost-user");
        var e = assertThrows(ApiException.class, () -> createWorkItem.execute(input, "lead-1", null));
        assertEquals("unknown_or_inactive", e.getMessage());
    }

    @Test void plannedHoursCannotBeSetOnAProjectEvenIfValid() {
        var input = new LinkedHashMap<String, Object>();
        input.put("type", "PROJECT"); input.put("title", "x"); input.put("plannedHours", new BigDecimal("5"));
        var e = assertThrows(ApiException.class, () -> createWorkItem.execute(input, "lead-1", null));
        assertEquals("parent_is_computed", e.getMessage());
    }
}
