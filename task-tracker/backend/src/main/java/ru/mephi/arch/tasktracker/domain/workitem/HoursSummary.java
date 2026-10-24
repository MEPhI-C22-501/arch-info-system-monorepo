package ru.mephi.arch.tasktracker.domain.workitem;

import java.math.BigDecimal;

public record HoursSummary(BigDecimal planned, BigDecimal actual, long unestimatedLeafCount) {
    public BigDecimal remaining() { return planned.subtract(actual); }
}
