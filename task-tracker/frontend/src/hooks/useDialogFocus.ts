import { useEffect, useRef } from 'react';
export function useDialogFocus(close:()=>void) {
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null;
    const dialog=ref.current;
    if(!dialog)return;
    const controls=()=>Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(el=>el.offsetParent!==null);
    (controls()[0] || dialog).focus();
    const keyboard=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();close();}
      if(event.key==='Tab'){
        const available=controls();const first=available[0],last=available[available.length-1];
        if(!first){event.preventDefault();return;}
        if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
        else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
      }
    };
    dialog.addEventListener('keydown',keyboard);
    return ()=>{dialog.removeEventListener('keydown',keyboard);previous?.focus();};
  },[close]);
  return ref;
}
