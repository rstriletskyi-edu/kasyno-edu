# Kasyno Edu

Run one command from the checkout:

```powershell
# Windows (PowerShell 5.1+)
.\scripts\start-dev.ps1
```

```bash
# Ubuntu
bash scripts/start-dev.sh
```

The scripts install missing tools and project dependencies, create **both**
`frontend/.env` and `backend/.env` from their examples, and start the app.
Existing settings and lockfiles are preserved. First startup needs internet access;
Ubuntu may ask for your sudo password. Tools are stored in ignored `.dev-tools/`.

- Frontend: http://localhost:4200
- API: http://localhost:8000/api
- API docs: http://localhost:8000/docs

**Firebase credentials are optional for startup.** The app and API health/docs work
without them. To enable login and Firebase features later, fill the public values in
`frontend/.env` and set `FIREBASE_CREDENTIALS_PATH` in `backend/.env` to your private
service-account JSON. Relative credential paths start from `backend/`.

Press **Ctrl+C** to stop both servers. Busy ports and failed servers are reported.
Use `-Install` (Windows) or `--install` (Ubuntu) to rerun dependency installation;
use `-Help` or `--help` for usage.

If Windows execution policy blocks the script, run this one-process exception:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

See [validation notes](docs/infrastructure/startup-validation.md) for tested cases and limitations.
