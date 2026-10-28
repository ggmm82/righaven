# Ricetta nativa FFmpeg

```bash
craft help ffmpeg
craft commands ffmpeg
craft tools ffmpeg --out "$RIGHAVEN_OUTPUT_DIR/work/ffmpeg-tools.json"
ffmpeg-cli call probe '{"input":"/mnt/user-data/outputs/JOB/movie.mp4","output":"/mnt/user-data/outputs/JOB/work/probe.json"}'
ffmpeg-cli call extract_audio '{"input":"/mnt/user-data/outputs/JOB/movie.mp4","output":"/mnt/user-data/outputs/JOB/work/audio.wav","sample_rate":48000,"channels":2}'
```

Usa percorsi reali e output nuovi. Il caso `ffmpeg` in `scripts/acceptance_toolkit.py` crea due media reali, esegue mux, probe, estrazione PCM e conversione di risoluzione/fps, verifica i flussi esportati e il rifiuto di sovrascrivere una consegna. Dopo delivery verifica la sincronizzazione per eventi significativi con riferimento; non viene certificata da un exit code zero.
