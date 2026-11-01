package ru.mephi.arch.tasktracker.application.workitem;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.workitem.support.*;
import ru.mephi.arch.tasktracker.domain.event.HierarchyChanged;
import ru.mephi.arch.tasktracker.domain.event.WorkItemFieldsChanged;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class UpdateWorkItemTest {
    private final InMemoryWorkItemRepository repo = new InMemoryWorkItemRepository();
    private final FakePermissionPort permissions = new FakePermissionPort();
    private final RecordingEventPublisher events = new RecordingEventPublisher();
    private final UpdateWorkItem updateWorkItem = new UpdateWorkItem(repo, FixedReferenceData.statuses(),
        FixedReferenceData.priorities(), FixedReferenceData.activeUsers("member-1"), permissions, events, new ViewWorkItem(repo));
    private UUID itemId;

    @BeforeEach void seedOneTask() {
        itemId = UUID.randomUUID();
        var item = new WorkItem(itemId, WorkItemType.TASK, "Original title", "", FixedReferenceData.DEFAULT_STATUS,
            FixedReferenceData.DEFAULT_PRIORITY, "member-1", null, null, null, null, null, null, null, null, null, null,
            0L, OffsetDateTime.now(), OffsetDateTime.now());
        repo.insert(item);
    }

    @Test void staleVersionIsRejected() {
        var input = new LinkedHashMap<String, Object>();
        input.put("version", "99"); input.put("title", "New title");
        var e = assertThrows(ApiException.class, () -> updateWorkItem.execute(itemId, input, "member-1", null));
        assertEquals("stale_work_item", e.getMessage());
    }

    @Test void noActualChangeRaisesNoEvent() {
        var input = new LinkedHashMap<String, Object>();
        input.put("title", "Original title");
        updateWorkItem.execute(itemId, input, "member-1", null);
        assertTrue(events.published.isEmpty());
    }

    @Test void changingStatusWithoutItemStatusPermissionIsRejected() {
        permissions.granted = java.util.Set.of("item.update");
        var input = new LinkedHashMap<String, Object>();
        input.put("statusId", UUID.randomUUID().toString());
        assertThrows(ApiException.class, () -> updateWorkItem.execute(itemId, input, "member-1", null));
    }

    @Test void changingTitleRaisesWorkItemFieldsChanged() {
        var input = new LinkedHashMap<String, Object>();
        input.put("title", "Renamed");
        updateWorkItem.execute(itemId, input, "member-1", null);
        var changes = events.ofType(WorkItemFieldsChanged.class);
        assertEquals(1, changes.size());
        assertEquals("Renamed", changes.getFirst().newValues().get("title"));
        assertEquals("Original title", changes.getFirst().oldValues().get("title"));
    }

    @Test void movingUnderANewEpicRaisesHierarchyChangedForBothParents() {
        UUID oldParent = UUID.randomUUID();
        UUID newParent = UUID.randomUUID();
        repo.insert(new WorkItem(oldParent, WorkItemType.EPIC, "Old epic", "", FixedReferenceData.DEFAULT_STATUS,
            FixedReferenceData.DEFAULT_PRIORITY, null, null, null, null, null, null, null, null, null, null, null,
            0L, OffsetDateTime.now(), OffsetDateTime.now()));
        repo.insert(new WorkItem(newParent, WorkItemType.EPIC, "New epic", "", FixedReferenceData.DEFAULT_STATUS,
            FixedReferenceData.DEFAULT_PRIORITY, null, null, null, null, null, null, null, null, null, null, null,
            0L, OffsetDateTime.now(), OffsetDateTime.now()));
        repo.getById(itemId).parentId = oldParent;

        var input = new LinkedHashMap<String, Object>();
        input.put("parentId", newParent.toString());
        updateWorkItem.execute(itemId, input, "member-1", null);

        var hierarchy = events.ofType(HierarchyChanged.class);
        assertEquals(2, hierarchy.size());
        assertTrue(hierarchy.stream().anyMatch(e -> e.workItemId().equals(oldParent)));
        assertTrue(hierarchy.stream().anyMatch(e -> e.workItemId().equals(newParent)));
    }

    @Test void reparentingUnderOwnSubtaskIsRejectedByTheHierarchyRuleBeforeAnyCycleCheck() {
        // the 4-level type hierarchy (PROJECT>EPIC>TASK/BUG>SUBTASK) makes a true cycle
        // structurally unreachable once isValidChildOf holds — this proves the use case still
        // wires that rule up against the real looked-up parent, not just the factory in isolation.
        UUID childId = UUID.randomUUID();
        repo.insert(new WorkItem(childId, WorkItemType.SUBTASK, "child", "", FixedReferenceData.DEFAULT_STATUS,
            FixedReferenceData.DEFAULT_PRIORITY, null, null, null, null, itemId, null, null, null, null, null, null,
            0L, OffsetDateTime.now(), OffsetDateTime.now()));
        var input = new LinkedHashMap<String, Object>();
        input.put("parentId", childId.toString());
        var e = assertThrows(ApiException.class, () -> updateWorkItem.execute(itemId, input, "member-1", null));
        assertEquals("invalid_hierarchy", e.getMessage());
    }

    @Test void repositoryLevelAncestryCheckDetectsASelfReferencingChain() {
        // isValidChildOf already makes a true cycle unreachable through the public use case, so
        // this exercises InMemoryWorkItemRepository.isAncestor directly instead.
        assertTrue(repo.isAncestor(itemId, itemId));
        assertFalse(repo.isAncestor(UUID.randomUUID(), itemId));
    }
}
