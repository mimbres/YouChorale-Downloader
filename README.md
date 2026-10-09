# YouChorale

YouChorale dataset contains 452 recordings of 261 compositions from 118 composers, representing a wide range of historical periods, styles, and complexities inherent to choral music.
![](https://github.com/ella-granger/YouChorale/blob/main/YouChorale.png)

## Download audio

Run with Python, yt-dlp (including its default extras), Node.js, FFmpeg and
FFprobe available in the execution environment:

```bash
python download_audio.py --output /path/to/you_chorale_yourmt3_16k
```

The tab-separated `info.csv` currently contains 496 links. Original audio is
saved as `<video_id>/source.<extension>` without trimming or resampling.
The downloader uses three retries after the initial attempt, validates the
entire audio before accepting it, and skips valid downloads when restarted.
Unavailable IDs and errors are printed at the end, with a nonzero exit status
if any download failed. Capture stdout and stderr to retain a run log.

Use `--id=VIDEO_ID` (repeatable) or `--limit N` for a small trial, `--retries N`
to change retry count, and `--cookies /path/to/cookies.txt` if YouTube requires
authentication. Keep cookies outside this repository.

The official split files contain 392 training, 30 validation and 30 test IDs.
The other 44 links have no assigned official split. Keep these assignments
when preparing learning datasets. Downloading does not convert annotations
or establish their timing accuracy.
