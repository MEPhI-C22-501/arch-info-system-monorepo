package ru.mephi.arch.tasktracker;

import org.springframework.web.bind.annotation.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.application.workitem.UpdateWorkItem;
import ru.mephi.arch.tasktracker.application.iteration.*;
import java.util.*;

@RestController
@RequestMapping("/api/v1/work-items/bulk")
public class BulkController {
    private final WorkItemRepository items;
    private final PermissionPort permissions;
    private final UpdateWorkItem update;
    private final AddWorkItemToIteration add;
    private final RemoveWorkItemFromIteration remove;
    private final TransactionTemplate tx;
    public BulkController(WorkItemRepository items, PermissionPort permissions, UpdateWorkItem update,
            AddWorkItemToIteration add, RemoveWorkItemFromIteration remove, PlatformTransactionManager manager) {
        this.items=items; this.permissions=permissions; this.update=update; this.add=add; this.remove=remove;
        tx=new TransactionTemplate(manager); tx.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }
    public record Entry(UUID id, Long version) {}
    public record Batch(String operation, Object value, List<Entry> items) {}
    @PostMapping public Object execute(@RequestBody Batch body) {
        if(body.operation()==null || !Set.of("status","assignee","iteration").contains(body.operation())) throw ApiException.invalid("operation","invalid");
        if(body.items()==null || body.items().isEmpty() || body.items().size()>100) throw ApiException.invalid("items","size_1_to_100");
        Set<UUID> seen=new HashSet<>();
        for(var e:body.items()) if(e==null || e.id()==null || e.version()==null || e.version()<0 || !seen.add(e.id())) throw ApiException.invalid("items","invalid_or_duplicate");
        List<Object> results=new ArrayList<>();
        for(var e:body.items()) {
            try {
                Long version=tx.execute(s->{
                    items.lockForUpdate(e.id()); var item=items.getById(e.id());
                    permissions.requireItemWritable(item.assigneeId);
                    if(item.version!=e.version()) throw ApiException.conflict("version","stale_work_item");
                    if(body.operation().equals("iteration")) {
                        permissions.require("iteration.write");
                        UUID target=Values.uuid(body.value(),"iterationId");
                        var current=items.findCurrentUnfinishedIterationId(e.id());
                        if(!Objects.equals(current.orElse(null),target)) {
                            current.ifPresent(id->remove.execute(id,e.id()));
                            if(target!=null) add.execute(target,e.id());
                        }
                    } else {
                        Map<String,Object> patch=new HashMap<>(); patch.put("version",e.version());
                        patch.put(body.operation().equals("status")?"statusId":"assigneeId",body.value());
                        update.execute(e.id(),patch,permissions.currentSubject(),null);
                    }
                    return items.getById(e.id()).version;
                });
                results.add(Map.of("id",e.id(),"success",true,"version",version));
            } catch(ApiException ex) {
                results.add(Map.of("id",e.id(),"success",false,"status",ex.status,"errors",List.of(Map.of("field",ex.field,"reason",ex.getMessage()))));
            } catch(RuntimeException ex) {
                java.util.logging.Logger.getLogger(BulkController.class.getName()).log(java.util.logging.Level.WARNING,"Bulk item failed: "+e.id(),ex);
                results.add(Map.of("id",e.id(),"success",false,"status",500,"errors",List.of(Map.of("field","item","reason","operation_failed"))));
            }
        }
        return Map.of("results",results);
    }
}
