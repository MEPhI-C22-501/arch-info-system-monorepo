package ru.mephi.arch.tasktracker;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.util.Map;

@RestController @RequestMapping("/api/v1")
public class ExcelController {
    private final ExcelService excel;
    public ExcelController(ExcelService excel){this.excel=excel;}
    @PostMapping("/exports/work-items") public ResponseEntity<byte[]> export(@RequestBody(required=false) Map<String,Object> body){return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename=task-tracker.xlsx").contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")).body(excel.export(body==null?Map.of():body));}
    @PostMapping("/imports/work-items") public ResponseEntity<?> importFile(@RequestParam("file") MultipartFile file){Map<String,Object> result=excel.importFile(file);return ResponseEntity.status(((Number)result.get("rejected")).intValue()>0?422:200).body(result);}
}
