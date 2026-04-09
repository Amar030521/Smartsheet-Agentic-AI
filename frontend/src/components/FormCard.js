import React, { useState, useCallback } from 'react';

const ACCENT = '#d4651a';
const BORDER = '1px solid #e8c4a0';
const FOCUS = { outline: 'none', borderColor: ACCENT, boxShadow: `0 0 0 3px rgba(212,101,26,0.12)` };

const inputBase = {
  width: '100%', boxSizing: 'border-box',
  padding: '9px 12px', fontSize: 13,
  border: BORDER, borderRadius: 8,
  background: '#fff', color: '#1a1a1a',
  transition: 'border-color 0.15s, box-shadow 0.15s',
  fontFamily: 'inherit'
};

function Field({ field, value, onChange, error }) {
  const [focused, setFocused] = useState(false);
  const style = { ...inputBase, ...(focused ? FOCUS : {}), ...(error ? { borderColor: '#ef4444' } : {}) };

  const handleChange = e => {
    const v = field.type === 'checkbox' ? e.target.checked : e.target.value;
    onChange(field.name, v);
  };

  const renderInput = () => {
    const fieldType = field.field_type || field.type || 'text';

    // CONTACT field with restricted contacts list
    if (fieldType === 'contact') {
      const contacts = field.options || [];
      if (contacts.length > 0) {
        return (
          <select value={value || ''} onChange={handleChange}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            style={{ ...style, cursor: 'pointer' }}>
            <option value="">Select contact...</option>
            {contacts.map((c, i) => (
              <option key={i} value={c.email || c.name || c}>
                {c.label || c.name || c}
              </option>
            ))}
          </select>
        );
      }
      // Unrestricted contact — free text email
      return (
        <input type="email" value={value || ''} onChange={handleChange}
          placeholder={field.placeholder || 'email@company.com'}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          style={style} />
      );
    }

    // PICKLIST / SELECT with options
    if (fieldType === 'select' || (field.options && field.options.length > 0 && fieldType !== 'contact')) {
      const opts = field.options || [];
      if (field.multi) {
        // Multi-select: show checkboxes
        const selected = Array.isArray(value) ? value : (value ? [value] : []);
        return (
          <div style={{ border: '1px solid #e8c4a0', borderRadius: 8, padding: '8px 10px', background: '#fff', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {opts.map(opt => (
              <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                <input type="checkbox" checked={selected.includes(opt)}
                  onChange={e => {
                    const next = e.target.checked
                      ? [...selected, opt]
                      : selected.filter(s => s !== opt);
                    onChange(field.name, next);
                  }}
                  style={{ width: 16, height: 16, accentColor: ACCENT }} />
                <span style={{ color: '#1a1a1a' }}>{opt}</span>
              </label>
            ))}
          </div>
        );
      }
      return (
        <select value={value || ''} onChange={handleChange}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          style={{ ...style, cursor: 'pointer' }}>
          <option value="">Select {field.label}...</option>
          {opts.map(opt => (
            <option key={typeof opt === 'object' ? opt.value : opt}
                    value={typeof opt === 'object' ? opt.value : opt}>
              {typeof opt === 'object' ? opt.label : opt}
            </option>
          ))}
        </select>
      );
    }

    switch (fieldType) {
      case 'textarea':
        return (
          <textarea value={value || ''} onChange={handleChange} rows={3}
            placeholder={field.placeholder || ''}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            style={{ ...style, resize: 'vertical', minHeight: 80, lineHeight: 1.5 }} />
        );

      case 'checkbox':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 4 }}>
            <input type="checkbox" checked={!!value}
              onChange={e => onChange(field.name, e.target.checked)}
              style={{ width: 18, height: 18, cursor: 'pointer', accentColor: ACCENT }} />
            <span style={{ fontSize: 13, color: '#7a4f30' }}>{field.checkbox_label || 'Yes'}</span>
          </div>
        );

      case 'date':
        return (
          <input type="date" value={value || ''} onChange={handleChange}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            style={style} />
        );

      case 'number':
        return (
          <input type="number" value={value || ''} onChange={handleChange}
            placeholder={field.placeholder || ''}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            style={style} />
        );

      case 'email':
        return (
          <input type="email" value={value || ''} onChange={handleChange}
            placeholder={field.placeholder || ''}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            style={style} />
        );

      default:
        return (
          <input type="text" value={value || ''} onChange={handleChange}
            placeholder={field.placeholder || ''}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            style={style} />
        );
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#2d1a0e', letterSpacing: '0.01em' }}>
          {field.label}
        </label>
        {field.required ? (
          <span style={{ fontSize: 11, color: '#ef4444', fontWeight: 700 }}>*</span>
        ) : (
          <span style={{ fontSize: 10, color: '#b07a55', fontWeight: 500, background: '#fff3ea', padding: '1px 7px', borderRadius: 20 }}>optional</span>
        )}
      </div>
      {field.hint && (
        <div style={{ fontSize: 11, color: '#b07a55', marginBottom: 2, lineHeight: 1.4 }}>{field.hint}</div>
      )}
      {renderInput()}
      {error && (
        <div style={{ fontSize: 11, color: '#ef4444', marginTop: 2 }}>{error}</div>
      )}
    </div>
  );
}

export default function FormCard({ form, onSubmit, onCancel }) {
  // Pre-fill defaults
  const initValues = {};
  (form.fields || []).forEach(f => {
    initValues[f.name] = f.value !== undefined ? f.value : (f.type === 'checkbox' ? false : '');
  });

  const [values, setValues] = useState(initValues);
  const [errors, setErrors] = useState({});
  const [preview, setPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = useCallback((name, value) => {
    setValues(prev => ({ ...prev, [name]: value }));
    setErrors(prev => ({ ...prev, [name]: undefined }));
  }, []);

  const validate = () => {
    const errs = {};
    (form.fields || []).forEach(f => {
      if (f.required && (values[f.name] === '' || values[f.name] === null || values[f.name] === undefined)) {
        errs[f.name] = `${f.label} is required`;
      }
      if (f.type === 'email' && values[f.name] && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values[f.name])) {
        errs[f.name] = 'Please enter a valid email address';
      }
    });
    return errs;
  };

  const handlePreview = () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setPreview(true);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    await onSubmit(form, values);
    setSubmitting(false);
  };

  const requiredFields = (form.fields || []).filter(f => f.required);
  const optionalFields = (form.fields || []).filter(f => !f.required);

  if (preview) {
    return (
      <div style={{ background: '#fff', border: BORDER, borderRadius: 14, overflow: 'hidden', marginTop: 8, maxWidth: 560 }}>
        {/* Preview header */}
        <div style={{ background: '#fff7f0', borderBottom: BORDER, padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 16 }}>👁️</span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#1a1a1a' }}>Review before submitting</div>
            <div style={{ fontSize: 12, color: '#b07a55', marginTop: 1 }}>{form.title}</div>
          </div>
        </div>

        {/* Preview table */}
        <div style={{ padding: '14px 18px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <tbody>
              {(form.fields || []).filter(f => values[f.name] !== '' && values[f.name] !== false).map((f, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f5e8dc' }}>
                  <td style={{ padding: '8px 0', color: '#7a4f30', fontWeight: 600, width: '40%', verticalAlign: 'top', paddingRight: 12 }}>
                    {f.label}
                    {f.required && <span style={{ color: '#ef4444', marginLeft: 3 }}>*</span>}
                  </td>
                  <td style={{ padding: '8px 0', color: '#1a1a1a', fontWeight: 500 }}>
                    {f.type === 'checkbox' ? (values[f.name] ? '✅ Yes' : '—') : (values[f.name] || '—')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Empty optional note */}
          {optionalFields.some(f => !values[f.name]) && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#b07a55', fontStyle: 'italic' }}>
              {optionalFields.filter(f => !values[f.name]).map(f => f.label).join(', ')} left empty (optional — can update later)
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button onClick={() => setPreview(false)} style={{
              padding: '9px 18px', fontSize: 13, borderRadius: 8, border: BORDER,
              background: '#fff', color: '#7a4f30', cursor: 'pointer', fontWeight: 600
            }}>← Edit</button>
            <button onClick={handleSubmit} disabled={submitting} style={{
              padding: '9px 24px', fontSize: 13, borderRadius: 8, border: 'none',
              background: submitting ? '#e8c4a0' : ACCENT, color: '#fff',
              cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 700, flex: 1
            }}>
              {submitting ? 'Submitting...' : (form.submit_label || 'Submit')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: '#fff', border: BORDER, borderRadius: 14, overflow: 'hidden', marginTop: 8, maxWidth: 560 }}>
      {/* Form header */}
      <div style={{ background: `linear-gradient(135deg, #b8511a, ${ACCENT})`, padding: '12px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{form.title}</div>
          {form.sheet_name && <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)', marginTop: 2 }}>Sheet: {form.sheet_name}</div>}
        </div>
        {onCancel && (
          <button onClick={onCancel} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: '#fff', fontSize: 18, cursor: 'pointer', borderRadius: 6, padding: '2px 8px', lineHeight: 1 }}>×</button>
        )}
      </div>

      <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Required fields */}
        {requiredFields.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#7a4f30', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: '#ef4444' }}>*</span> Required fields
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {requiredFields.map(f => (
                <Field key={f.name} field={f} value={values[f.name]} onChange={handleChange} error={errors[f.name]} />
              ))}
            </div>
          </div>
        )}

        {/* Divider if both sections exist */}
        {requiredFields.length > 0 && optionalFields.length > 0 && (
          <div style={{ height: 1, background: '#f0d5be', margin: '4px 0' }} />
        )}

        {/* Optional fields */}
        {optionalFields.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#b07a55', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
              Optional fields (can fill later)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {optionalFields.map(f => (
                <Field key={f.name} field={f} value={values[f.name]} onChange={handleChange} error={errors[f.name]} />
              ))}
            </div>
          </div>
        )}

        {/* Status fields note */}
        {form.auto_fields?.length > 0 && (
          <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 8, padding: '8px 12px', fontSize: 11, color: '#0369a1' }}>
            ℹ️ <strong>{form.auto_fields.join(', ')}</strong> will be set automatically by Smartsheet — no input needed.
          </div>
        )}

        {/* Error summary */}
        {Object.keys(errors).length > 0 && (
          <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '8px 12px', fontSize: 12, color: '#dc2626' }}>
            Please fill in the required fields marked above.
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 10, paddingTop: 4 }}>
          {onCancel && (
            <button onClick={onCancel} style={{
              padding: '9px 16px', fontSize: 13, borderRadius: 8, border: BORDER,
              background: '#fff', color: '#7a4f30', cursor: 'pointer', fontWeight: 600
            }}>Cancel</button>
          )}
          <button onClick={handlePreview} style={{
            padding: '9px 0', fontSize: 13, borderRadius: 8, border: 'none',
            background: ACCENT, color: '#fff', cursor: 'pointer', fontWeight: 700, flex: 1
          }}>
            Review & Submit →
          </button>
        </div>
      </div>
    </div>
  );
}
