package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

public interface TypeSettingRepository {
    boolean isEnabled(WorkItemType type);
}
