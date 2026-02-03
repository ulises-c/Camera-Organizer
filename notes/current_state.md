## Dry Run

Front end - dry run, clicked cancel to see if that frees the process

```log
[15:57:19] Selected: /Users/ulises/Downloads/Photo-Org-Test/1996 copy 9
[15:57:25] Starting process (dry_run=True)...
[16:01:07] Cancellation requested...
```

Back end - dry run

```sh
✅ ALL CHECKS PASSED - Environment is healthy!

🚀 Launching photo-organizer...
🚀 Launched photo_organizer.converter.gui (PID 75018)
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Selected: /Users/ulises/Downloads/Photo-Org-Test/1996 copy 10
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Starting process (dry_run=True)...
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Process initialized; beginning conversion.
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Processing group [1/2]: 1996_0002
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  → Selected: 1996_0002_a.tif (quality_score)
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Processing group [2/2]: 1996_0001
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  → Selected: 1996_0001_a.tif (quality_score)
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Report saved: report_20260202_165013.json
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Complete.
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Cancellation requested...
```

## Live Run

Front end - live run

```log
[16:02:31] Selected: /Users/ulises/Downloads/Photo-Org-Test/1996 copy 9
[16:02:38] Starting process (dry_run=False)...
[16:03:05] Cancellation requested...
```

Back end - live run

```sh
✅ ALL CHECKS PASSED - Environment is healthy!

🚀 Launching photo-organizer...
🚀 Launched photo_organizer.converter.gui (PID 82574)
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Selected: /Users/ulises/Downloads/Photo-Org-Test/1996 copy 13
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Starting process (dry_run=False)...
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Process initialized; beginning conversion.
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Processing group [1/2]: 1996_0002
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  → Selected: 1996_0002_a.tif (quality_score)
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  Error (TIFF): 'NoneType' object is not iterable
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  Error (TIFF): 'NoneType' object is not iterable
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Processing group [2/2]: 1996_0001
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  → Selected: 1996_0001_a.tif (quality_score)
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  Error (TIFF): 'NoneType' object is not iterable
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  Error (TIFF): 'NoneType' object is not iterable
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:  Error (TIFF): 'NoneType' object is not iterable
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Report saved: report_20260202_181542.json
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Complete.
[photo_organizer.converter.gui] INFO:photo_organizer.converter.gui:Cancellation requested...
🏁 photo_organizer.converter.gui exited with code 0
```
