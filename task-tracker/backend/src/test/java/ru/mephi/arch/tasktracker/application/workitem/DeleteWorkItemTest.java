package ru.mephi.arch.tasktracker.application.workitem;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.workitem.support.FakePermissionPort;
import ru.mephi.arch.tasktracker.application.workitem.support.InMemoryWorkItemRepository;
import ru.mephi.arch.tasktracker.application.workitem.support.RecordingEventPublisher;
import ru.mephi.arch.tasktracker.domain.event.HierarchyChanged;
import ru.mephi.arch.tasktracker.domain.event.WorkItemHardDeleted;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.time.OffsetDateTime;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class DeleteWorkItemTest {
    private final InMemoryWorkItemRepository repo = new InMemoryWorkItemRepository();
    private final FakePermissionPort permissions = new FakePermissionPort();
    private final RecordingEventPublisher events = new RecordingEventPublisher();
    private final DeleteWorkItem deleteWorkItem = new DeleteWorkItem(repo, permissions, events);
    private UUID itemId;

    @BeforeEach void seedOneTask() {
        permissions.role = "ADMIN";
        itemId = UUID.randomUUID();
        repo.insert(new WorkItem(itemId, WorkItemType.TASK, "To delete", "", UUID.randomUUID(), UUID.randomUUID(),
            "member-1", null, null, null, null, null, null, null, null, null, null, 0L,
            OffsetDateTime.now(), OffsetDateTime.now()));
    }

    @Test void wrongConfirmationIsRejectedAndNothingIsDeleted() {
        var e = assertThrows(ApiException.class, () -> deleteWorkItem.execute(itemId, "not-the-id"));
        assertEquals("confirmation_required", e.getMessage());
        assertTrue(repo.items.containsKey(itemId));
    }

    @Test void deletingAnItemWithChildrenIsBlocked() {
        repo.insert(new WorkItem(UUID.randomUUID(), WorkItemType.SUBTASK, "child", "", UUID.randomUUID(), UUID.randomUUID(),
            null, null, null, null, itemId, null, null, null, null, null, null, 0L, OffsetDateTime.now(), OffsetDateTime.now()));
        var e = assertThrows(ApiException.class, () -> deleteWorkItem.execute(itemId, itemId.toString()));
        assertEquals("move_or_delete_children_first", e.getMessage());
        assertTrue(repo.items.containsKey(itemId));
    }

    @Test void successfulDeleteRemovesTheItemAndNotifiesTheAssigneeWithASnapshot() {
        deleteWorkItem.execute(itemId, itemId.toString());
        assertFalse(repo.items.containsKey(itemId));
        var notifications = events.ofType(WorkItemHardDeleted.class);
        assertEquals(1, notifications.size());
        assertEquals("member-1", notifications.getFirst().recipientId());
        assertEquals("To delete", notifications.getFirst().title());
        assertTrue(events.ofType(HierarchyChanged.class).isEmpty());
    }

    @Test void deletingAChildTouchesAndNotifiesItsParent() {
        UUID parentId = UUID.randomUUID();
        repo.insert(new WorkItem(parentId, WorkItemType.EPIC, "Parent", "", UUID.randomUUID(), UUID.randomUUID(),
            null, null, null, null, null, null, null, null, null, null, null, 0L, OffsetDateTime.now(), OffsetDateTime.now()));
        repo.getById(itemId).parentId = parentId;

        deleteWorkItem.execute(itemId, itemId.toString());

        var hierarchy = events.ofType(HierarchyChanged.class);
        assertEquals(1, hierarchy.size());
        assertEquals(parentId, hierarchy.getFirst().workItemId());
        assertEquals(1, repo.touchCount);
    }

    @Test void requiresItemDeletePermission() {
        permissions.role = "MEMBER";
        permissions.granted = java.util.Set.of("item.read");
        assertThrows(ApiException.class, () -> deleteWorkItem.execute(itemId, itemId.toString()));
    }
}
