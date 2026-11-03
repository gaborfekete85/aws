import { useEffect, useRef, type ReactNode } from 'react'

/** Accessible confirmation modal (native <dialog>), instead of window.confirm. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  danger,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '') // jsdom
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [open])

  return (
    <dialog ref={ref} className="card dialog" aria-labelledby="confirm-title" onCancel={onCancel}>
      {open && (
        <>
          <h2 id="confirm-title">{title}</h2>
          <div>{children}</div>
          <div className="dialog-actions">
            <button type="button" className="secondary" onClick={onCancel}>
              Keep it
            </button>
            <button type="button" className={danger ? 'danger' : undefined} onClick={onConfirm}>
              {confirmLabel}
            </button>
          </div>
        </>
      )}
    </dialog>
  )
}
