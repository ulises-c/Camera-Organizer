**GUI Compatibility Rules (CRITICAL):**

Environment: macOS M-series (Tcl/Tk 9.0.3), Linux (various)
Framework: tkinter + ttkbootstrap

NEVER pass `padding=` as a constructor argument to:

- ttk.LabelFrame
- ttk.Button
- Any ttk widget that might not support it

ALWAYS use one of these patterns instead:

1. Inner frame: `inner = ttk.Frame(parent, padding=10); inner.pack(fill=X)`
2. Pack options: `widget.pack(fill=X, padx=10, pady=10)`

Before finishing, verify that the code would run on:

- macOS with Tcl/Tk 9.0+
- Linux with Tcl/Tk 8.6+

Test command: `poetry run python -m photo_organizer.converter.gui`
