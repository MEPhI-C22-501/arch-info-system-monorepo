package ru.mephi.arch.tasktracker;

import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ExcelServiceTest {
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
