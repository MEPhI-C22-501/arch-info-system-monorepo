package ru.mephi.arch.tasktracker.domain.iteration;

import java.math.BigDecimal;

public record CapacityEntry(String externalUserId, BigDecimal availableHours) {
}
