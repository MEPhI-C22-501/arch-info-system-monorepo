package ru.mephi.arch.tasktracker.application.port;

public interface UserDirectoryRepository {
    boolean isActive(String externalUserId);
}
