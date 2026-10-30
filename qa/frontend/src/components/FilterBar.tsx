import { useEffect, useRef, useState } from 'react';
import type { Option } from '../useReferenceData';

export type FilterField =
  | { name: string; label: string; type: 'select'; options: Option[]; emptyLabel: string }
  | { name: string; label: string; type: 'text'; placeholder?: string; suggestions?: string[]; upperCase?: boolean };

type Props = {
  fields: FilterField[];
  values: Record<string, string | undefined>;
  onChange: (name: string, value: string) => void;
  onReset?: () => void;
};

const TYPING_DELAY_MS = 300;

function TextFilter({ value, onChange, upperCase, ...rest }: { value: string; onChange: (value: string) => void; upperCase?: boolean; placeholder?: string; list?: string }) {
  const [text, setText] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => setText(value), [value]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const apply = () => {
    clearTimeout(timer.current);
    if (text.trim() !== value) onChange(text.trim());
  };

  return (
    <input
      type="text"
      {...rest}
      value={text}
      onChange={(event) => {
        const next = upperCase ? event.target.value.toUpperCase() : event.target.value;
        setText(next);
        clearTimeout(timer.current);
        timer.current = setTimeout(() => onChange(next.trim()), TYPING_DELAY_MS);
      }}
      onBlur={apply}
      onKeyDown={(event) => {
        // Фильтр бывает внутри формы: Enter применяет его, а не отправляет форму.
        if (event.key === 'Enter') {
          event.preventDefault();
          apply();
        }
      }}
    />
  );
}

export function FilterBar({ fields, values, onChange, onReset }: Props) {
  return (
    <div className="bar filters" role="search">
      {fields.map((field) => (
        <label key={field.name} className="filter">
          {field.label}
          {field.type === 'select' ? (
            // Варианты могут прийти после значения из адреса: React выставит его только новому select.
            <select key={field.options.length} value={values[field.name] ?? ''} onChange={(event) => onChange(field.name, event.target.value)}>
              <option value="">{field.emptyLabel}</option>
              {field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          ) : (
            <>
              <TextFilter
                value={values[field.name] ?? ''}
                onChange={(value) => onChange(field.name, value)}
                placeholder={field.placeholder}
                upperCase={field.upperCase}
                list={field.suggestions ? `${field.name}-suggestions` : undefined}
              />
              {field.suggestions && (
                <datalist id={`${field.name}-suggestions`}>
                  {field.suggestions.map((value) => <option key={value} value={value} />)}
                </datalist>
              )}
            </>
          )}
        </label>
      ))}
      {onReset && <button type="button" onClick={onReset}>Сбросить</button>}
    </div>
  );
}
