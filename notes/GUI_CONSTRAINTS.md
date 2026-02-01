# GUI Compatibility Rules (CRITICAL)

**Environment:** macOS M-series (Tcl/Tk 9.0.3), Linux (various)  
**Framework:** tkinter + ttkbootstrap

## 1. Namespace Safety (CRITICAL - Prevents UnboundLocalError)

**NEVER** use wildcard imports for tkinter/ttkbootstrap constants:

```python
# ❌ WRONG - causes UnboundLocalError
from tkinter import *
from ttkbootstrap.constants import *

def _create_widgets(self):
    widget.pack(side=RIGHT)  # UnboundLocalError!
```

**ALWAYS** use explicit `tk.` namespace:

```python
# ✅ CORRECT
import tkinter as tk

def _create_widgets(self):
    widget.pack(side=tk.RIGHT, fill=tk.X, expand=tk.YES)
```

## 2. Bootstyle Safety (CRITICAL - Prevents TclError)

**NEVER** pass `bootstyle` directly to container widgets like `LabelFrame`:

```python
# ❌ WRONG - causes TclError on some platforms
frame = ttk.LabelFrame(parent, text="Title", bootstyle="danger")
```

**ALWAYS** use a safe wrapper or omit bootstyle on containers:

```python
# ✅ CORRECT - use safe wrapper
def safe_widget_create(widget_cls, *args, bootstyle=None, **kwargs):
    if bootstyle:
        try:
            return widget_cls(*args, bootstyle=bootstyle, **kwargs)
        except (TypeError, tk.TclError):
            return widget_cls(*args, **kwargs)
    return widget_cls(*args, **kwargs)

# Or simply omit bootstyle on LabelFrame
frame = ttk.LabelFrame(parent, text="Title")
```

## 3. Padding Constraints

**NEVER** pass `padding=` as a constructor argument to `ttk.LabelFrame`:

```python
# ❌ WRONG
frame = ttk.LabelFrame(parent, text="Title", padding=10)
```

**ALWAYS** use inner frames for padding:

```python
# ✅ CORRECT
frame = ttk.LabelFrame(parent, text="Title")
inner = ttk.Frame(frame, padding=10)
inner.pack(fill=tk.X)
```

## 4. Packing Order (Visibility)

To ensure bottom toolbars/buttons remain visible:

1. Pack fixed toolbars with `side=tk.BOTTOM` **FIRST**
2. Pack expanding content containers **AFTER**

```python
# ✅ CORRECT ORDER
bottom_toolbar = ttk.Frame(root)
bottom_toolbar.pack(side=tk.BOTTOM, fill=tk.X)  # FIRST

main_content = ttk.Frame(root)
main_content.pack(fill=tk.BOTH, expand=tk.YES)  # AFTER
```

## 5. Toggle Consistency

Use uniform `bootstyle` variants for all toggles:

- `"success-round-toggle"` for standard options
- `"warning-round-toggle"` for caution options
- `"danger-round-toggle"` for safety-critical options (dry run)

## 6. Dry Run Mode Requirements

- Default to dry-run mode (enabled on startup)
- Log dry-run status on init and when toggled
- Show visual banner indicating current mode
- Require confirmation dialog when disabling dry-run
- Update button text and colors dynamically based on mode

## 7. Testing Checklist

Before committing GUI changes, verify:

- [ ] No `UnboundLocalError` or namespace-related errors
- [ ] No `_tkinter.TclError` about unknown options
- [ ] Start/primary action buttons visible on default window size
- [ ] Dry-run status logs at startup and on toggle
- [ ] Toggles have uniform appearance
- [ ] Works on macOS (Tcl/Tk 9.0+) and Linux (Tcl/Tk 8.6+)

## 8. Quick Reference

| Issue | Cause | Solution |
|-------|-------|----------|
| UnboundLocalError | Wildcard imports | Use `tk.RIGHT` not `RIGHT` |
| TclError bootstyle | Direct pass to container | Use safe_widget_create helper |
| Hidden buttons | Wrong pack order | Pack toolbar FIRST with side=tk.BOTTOM |
| Padding crash | padding= on LabelFrame | Use inner Frame with padding |
