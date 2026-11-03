package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.SimpleTransactionStatus;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.application.workitem.UpdateWorkItem;
import ru.mephi.arch.tasktracker.application.iteration.*;
import ru.mephi.arch.tasktracker.domain.workitem.*;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class BulkControllerTest {
    private final WorkItemRepository items=mock(WorkItemRepository.class);
    private final PermissionPort permissions=mock(PermissionPort.class);
    private final UpdateWorkItem update=mock(UpdateWorkItem.class);
    private final PlatformTransactionManager manager=mock(PlatformTransactionManager.class);
    private BulkController controller() {
        when(manager.getTransaction(any())).thenAnswer(i->new SimpleTransactionStatus());
        return new BulkController(items,permissions,update,mock(AddWorkItemToIteration.class),mock(RemoveWorkItemFromIteration.class),manager);
    }
    @Test void duplicateIdsRejectTheWholeRequestBeforeAnyWrite() {
        UUID id=UUID.randomUUID(); var c=controller();
        assertThrows(ApiException.class,()->c.execute(new BulkController.Batch("status",UUID.randomUUID(),List.of(new BulkController.Entry(id,0L),new BulkController.Entry(id,0L)))));
        verifyNoInteractions(items,update);
    }
    @Test void staleTaskDoesNotPreventNextTaskFromBeingProcessed() {
        UUID stale=UUID.randomUUID(),valid=UUID.randomUUID();
        when(items.getById(stale)).thenReturn(item(stale,2)); when(items.getById(valid)).thenReturn(item(valid,0));
        Object result=controller().execute(new BulkController.Batch("status",UUID.randomUUID(),List.of(new BulkController.Entry(stale,0L),new BulkController.Entry(valid,0L))));
        var rows=(List<?>)((Map<?,?>)result).get("results");
        assertEquals(false,((Map<?,?>)rows.get(0)).get("success")); assertEquals(true,((Map<?,?>)rows.get(1)).get("success"));
        verify(update,times(1)).execute(eq(valid),anyMap(),any(),isNull());
        verify(manager,times(1)).rollback(any()); verify(manager,times(1)).commit(any());
    }
    private WorkItem item(UUID id,long version) { return new WorkItem(id,WorkItemType.TASK,"Task","",UUID.randomUUID(),UUID.randomUUID(),"member",null,null,null,null,null,null,null,null,null,null,version,null,null); }
}
