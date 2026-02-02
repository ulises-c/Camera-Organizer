# GUI Compatibility Rules (CRITICAL)

**Environment:** macOS M-series (Tcl/Tk 9.0.3), Linux (various)  
**Framework:** tkinter + ttkbootstrap

## 1. Namespace Safety (CRITICAL)

**ALWAYS** use explicit `tk.` namespace for constants (e.g., `tk.RIGHT`, `tk.X`).

## 2. Bootstyle Safety (CRITICAL)

**NEVER** pass `bootstyle` directly to container widgets like `LabelFrame`.
**ALWAYS** use the `safe_widget_create` wrapper.

## 3. Padding & Dimension Constraints

- **NEVER** use `padding=` on `ttk.LabelFrame`. Use an inner `ttk.Frame`.
- **NEVER** use `width=` on `ttk.Scale` or `ttk.Progressbar`. Use `length=` for pixel dimensions.
- **NEVER** use `width=` on `ttk.Label`. Use `wraplength=` or layout management.

## 4. Packing Order (Visibility)

1. Pack bottom toolbars/buttons **FIRST** with `side=tk.BOTTOM`.
2. Pack main content **SECOND** with `fill=tk.BOTH, expand=tk.YES`.

## 5. Widget Construction Wrapper

Use this robust version to handle incompatible options across platforms:

```python
def safe_widget_create(widget_cls, parent, **kwargs):
    """
    Robust widget creator handling macOS/Linux incompatibilities.
    Automatically maps 'width' to 'length' for Scale/Progressbar.
    """
    # 1. Map incompatible options
    widget_name = getattr(widget_cls, "__name__", str(widget_cls))
    if widget_name in ('Scale', 'Progressbar') and 'width' in kwargs:
        if 'length' not in kwargs:
            kwargs['length'] = kwargs.pop('width')
        else:
            kwargs.pop('width') # Prefer explicit length if both exist

    # 2. Try with bootstyle
    bootstyle = kwargs.pop('bootstyle', None)
    try:
        if bootstyle:
            return widget_cls(parent, bootstyle=bootstyle, **kwargs)
        return widget_cls(parent, **kwargs)
    except (tk.TclError, TypeError):
        # 3. Fallback: strip bootstyle and retry
        # If that fails, the caller receives the error (we can't guess valid args)
        return widget_cls(parent, **kwargs)
```

## 6. Toggle Consistency

Use uniform `bootstyle` variants for all toggles:

- `"success-round-toggle"` for standard options
- `"warning-round-toggle"` for caution options
- `"danger-round-toggle"` for safety-critical options (dry run)

## 7. Dry Run Mode Requirements

- Default to dry-run mode (enabled on startup)
- Log dry-run status on init and when toggled
- Show visual banner indicating current mode
- Require confirmation dialog when disabling dry-run
- Update button text and colors dynamically based on mode

## 8. Testing Checklist

Before committing GUI changes, verify:

- [ ] No `UnboundLocalError` or namespace-related errors
- [ ] No `_tkinter.TclError` about unknown options
- [ ] Start/primary action buttons visible on default window size
- [ ] Dry-run status logs at startup and on toggle
- [ ] Toggles have uniform appearance
- [ ] Works on macOS (Tcl/Tk 9.0+) and Linux (Tcl/Tk 8.6+)

## 9. Quick Reference

| Issue              | Cause                    | Solution                               |
| ------------------ | ------------------------ | -------------------------------------- |
| UnboundLocalError  | Wildcard imports         | Use `tk.RIGHT` not `RIGHT`             |
| TclError bootstyle | Direct pass to container | Use safe_widget_create helper          |
| Hidden buttons     | Wrong pack order         | Pack toolbar FIRST with side=tk.BOTTOM |
| Padding crash      | padding= on LabelFrame   | Use inner Frame with padding           |
