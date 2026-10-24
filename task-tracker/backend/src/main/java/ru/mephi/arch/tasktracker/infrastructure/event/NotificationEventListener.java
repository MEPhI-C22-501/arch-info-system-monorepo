package ru.mephi.arch.tasktracker.infrastructure.event;

import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import ru.mephi.arch.tasktracker.application.port.NotificationRepository;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.event.RecordableChange;
import ru.mephi.arch.tasktracker.domain.event.WorkItemHardDeleted;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;

@Component
public class NotificationEventListener {
    private final NotificationRepository notifications;
    private final WorkItemRepository workItems;
    public NotificationEventListener(NotificationRepository notifications, WorkItemRepository workItems) {
        this.notifications = notifications; this.workItems = workItems;
    }

    @EventListener
    public void on(RecordableChange event) {
        WorkItem item = workItems.getById(event.workItemId());
        if (item.assigneeId == null) return;
        notifications.create(item.assigneeId, item.id, item.id.toString(), item.title, event.message(),
            event.actorId(), OffsetDateTime.now(ZoneOffset.UTC));
    }

    @EventListener
    public void on(WorkItemHardDeleted event) {
        if (event.recipientId() == null) return;
        notifications.create(event.recipientId(), null, event.workItemPublicId(), event.title(),
            "Рабочий элемент удалён", event.actorId(), OffsetDateTime.now(ZoneOffset.UTC));
    }
}
