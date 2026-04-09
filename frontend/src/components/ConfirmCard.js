import React from 'react';

export default function ConfirmCard({ message, onConfirm, onCancel }) {
  return (
    <div className="confirm-card">
      <div className="confirm-title">
        ⚠️ Confirmation Required
      </div>
      <div className="confirm-desc">
        {message || 'This action will make changes to your Smartsheet workspace. Do you want to proceed?'}
      </div>
      <div className="confirm-actions">
        <button className="btn-confirm" onClick={onConfirm}>
          ✓ Yes, proceed
        </button>
        <button className="btn-cancel" onClick={onCancel}>
          ✕ Cancel
        </button>
      </div>
    </div>
  );
}
