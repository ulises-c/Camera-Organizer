# TIFF Converter

Desired Workflow:

1. Select folder
2. Select file output options
   1. TIFF conversion toggle (on by default)
      1. compression algorithm (lossless only, tooltip explaining difference between algorithm, default to best algorithm)
         1. LZW gets `<file>.LZW.TIF`
         2. Deflate gets `<file>.ZIP.TIF`, just a suggestion to use ZIP, if something else is standard or more appropriate use that.
   2. HEIC conversion toggle (on by default)
      1. Quality: 100% by default
      2. Create folder if enabled
   3. JPG conversion toggle (off by default)
      1. Select reasonable default parameters
      2. Create folder if enabled
3. Creates copies of all photos to compressed (this is not an options, it's the required default behavior)
   1. Typical use case for most scanners, extra options for FastFoto scans below
4. Enable/Disable FastFoto Workflow (since FastFoto can create augmented and backside scans)
   1. Archiving mode (radio button): "Smart" (default), "Base", "Augment, "None"
      1. Smart uses an automated smart analysis comparing base to augmented
   2. Enable/Disable variant smart archiving
      1. This creates a subfolder in `lossless_compressed/` called `archive/`, and stores the selected variants that weren't selected (radio button)
   3. Enable/disable variant smart conversion
      1. Sub-toggle for variant selection
      2. If enabled, only the "selects" are converted to HEIC/JPG (depending on output options)
      3. If disabled, all photos are converted to HEIC/JPG
5. Store originals in `originals/`
