# Troubleshooting

Common problems and fixes when running VoiceOS.

---

## Doctor first

Always run:

```bash
voiceos-doctor
```

Fix **FAIL** items before **WARN** items when possible.

---

## Installation

### `python` or `pip` not found

- Reinstall Python 3.10+ and enable **Add to PATH** (Windows).  
- On Mac/Linux use `python3` and `pip3`.  
- Restart the terminal after installing Python.

### `voiceos` command not found

```bash
pip install -e .
```

Ensure your virtual environment is activated (`(.venv)` in the prompt).

### PowerShell cannot run scripts

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Voice and microphone

### No microphone detected

- Check OS privacy settings (allow microphone for Terminal/Python).  
- Use CLI-only mode: `voiceos --mode cli`  
- Set `MICROPHONE_DEVICE` in `.env` if you have multiple devices.

### Wake word does not respond

- Start with `voiceos-shell` or enable shell in config.  
- Say the full phrase: **“hey voiceos”** then pause, then your command.  
- Or set `VOICEOS_SHELL_INPUT_MODE=always_on` for testing.

### TTS silent or errors

- Kokoro/Coqui may need extra setup on first run.  
- Check `logs/voiceos.log`.  
- CLI responses still appear as text in the terminal.

---

## LLM / AI brain

### “Cannot connect to LLM” or slow responses

1. Start Ollama: `ollama serve`  
2. Pull a model: `ollama pull mistral`  
3. Match `.env`: `LLM_ENDPOINT=http://localhost:11434/api/generate`  
4. Or set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for cloud.

### Out of memory

- Use a smaller Whisper model: `WHISPER_MODEL=tiny` or `base`  
- Use a smaller LLM via Ollama  
- Enable Docker workers so heavy tasks leave the host RAM

---

## Docker and workers

### Doctor shows `local_only`

- Start Docker Desktop.  
- Run `voiceos-compute` or `start_hybrid` script.  
- Set `EXECUTION_MODE=auto` in `.env`.

### Workers not registering

```bash
docker compose --profile core up -d
docker compose --profile workers up -d
voiceos-doctor
```

Check `REDIS_URL` matches compose (default port 6379).

### Heavy task still slow on host

- Confirm doctor tier is `full_hybrid`.  
- Check `voiceos --status` for worker count and queue depth.

---

## Permissions and policy

### Everything asks for approval

- Normal for `work` profile or HIGH permission tools.  
- Set `VOICEOS_POLICY_PROFILE=personal` for fewer prompts.  
- Do **not** use `unattended` on a shared desktop without understanding auto-deny behavior.

### Action blocked with no prompt

- `unattended` profile auto-denies risky actions.  
- Workers never run OS tools — run desktop commands on the host.

---

## Host bridge

### Bridge not running (WARN in doctor)

Optional service. Start if needed:

```bash
voiceos-bridge
# or
.\scripts\start_bridge.ps1
```

Set `VOICEOS_BRIDGE_MODE=local` to skip bridge entirely.

---

## Logs

| File | Contents |
|------|----------|
| `logs/voiceos.log` | General application log |
| `logs/audit.log` | Permissions and policy events |

Export audit:

```bash
voiceos-audit-export --since-hours 24
```

---

## Still stuck?

1. `voiceos --status`  
2. `python main.py --test`  
3. `python -m pytest tests/ -q`  
4. Open a GitHub issue with doctor output (remove secrets from `.env`)
