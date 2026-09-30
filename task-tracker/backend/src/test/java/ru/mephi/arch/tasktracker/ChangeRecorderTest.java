package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.Test;
import java.sql.Date;
import java.time.LocalDate;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class ChangeRecorderTest {
    @Test void iterationSnapshotWithJdbcDatesCanBeSerializedAndRead() {
        ChangeRecorder recorder = new ChangeRecorder(null);
        String json = recorder.json(Map.of("startDate", Date.valueOf(LocalDate.of(2026, 9, 28)), "plannedHours", 5));
        Map<String,Object> restored = recorder.parseMap(json);
        assertEquals(5, restored.get("plannedHours"));
        assertTrue(restored.containsKey("startDate"));
    }
}
