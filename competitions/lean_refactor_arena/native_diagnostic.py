"""Best-effort compiler diagnostics; never replace native harness authority."""
import subprocess

def text(value):
    if isinstance(value,bytes):return value.decode('utf-8',errors='replace')
    return value or ''

def capture(command,cwd,runner=subprocess.run,timeout=240):
    try:
        p=runner(command,cwd=cwd,capture_output=True,text=True,timeout=timeout)
        return dict(status='completed',returncode=p.returncode,output=text(p.stdout)+'\n'+text(p.stderr))
    except subprocess.TimeoutExpired as exc:
        return dict(status='timeout',returncode=None,output=text(exc.stdout)+'\n'+text(exc.stderr))
    except OSError as exc:
        return dict(status='unavailable',returncode=None,output=str(exc))
