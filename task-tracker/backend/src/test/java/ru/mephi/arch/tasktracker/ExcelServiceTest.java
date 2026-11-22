package ru.mephi.arch.tasktracker;

import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.Map;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ExcelServiceTest {
    @Test void importPreservesMarkdownAndAllowsDefaultsForNewRows() throws Exception {
        var items = mock(WorkItemService.class);
        var access = mock(AccessService.class);
        when(access.subject()).thenReturn("lead");
        var excel = new ExcelService(mock(JdbcTemplate.class), access, items, mock(IterationService.class));
        UUID id = UUID.randomUUID();
        when(items.createAs(anyMap(), eq("lead"), isNull())).thenReturn(Map.of("id", id));
        when(items.view(id)).thenReturn(Map.of());
        String description = "    code block\n\n  ";
        byte[] input;
        try (var workbook = new XSSFWorkbook(new ByteArrayInputStream(excel.export(Map.of())));
             var bytes = new ByteArrayOutputStream()) {
            var row = workbook.getSheet("WorkItems").createRow(4);
            row.createCell(2).setCellValue("TASK");
            row.createCell(3).setCellValue("New task");
            row.createCell(4).setCellValue(description);
            workbook.write(bytes);
            input = bytes.toByteArray();
        }
        var report = excel.importFile(new MockMultipartFile("file", "test.xlsx", "application/octet-stream", input));
        assertEquals(1, report.get("created"));
        verify(items).createAs(argThat(fields -> description.equals(fields.get("description"))
            && !fields.containsKey("statusId") && !fields.containsKey("priorityId")), eq("lead"), isNull());
    }

    @Test void formulaInImportedWorkbookIsRejectedBeforeAnyItemMutation() throws Exception {
        JdbcTemplate db = mock(JdbcTemplate.class);
        WorkItemService items = mock(WorkItemService.class);
        IterationService iterations = mock(IterationService.class);
        ExcelService excel = new ExcelService(db, mock(AccessService.class), items, iterations);
        byte[] template = excel.export(Map.of());
        byte[] input;
        try (var workbook = new XSSFWorkbook(new ByteArrayInputStream(template));
             var bytes = new ByteArrayOutputStream()) {
            var row = workbook.getSheet("WorkItems").createRow(1);
            row.createCell(2).setCellValue("TASK");
            row.createCell(3).setCellValue("Test task");
            row.createCell(4).setCellFormula("1+1");
            workbook.write(bytes);
            input = bytes.toByteArray();
        }
        var report = excel.importFile(new MockMultipartFile("file", "test.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", input));
        assertEquals(0, report.get("created"));
        assertEquals(0, report.get("updated"));
        assertEquals(1, report.get("rejected"));
        assertTrue(report.get("errors").toString().contains("formula_not_allowed"));
        verifyNoInteractions(items, iterations);
    }
}
