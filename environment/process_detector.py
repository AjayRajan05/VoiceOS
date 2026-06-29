import psutil
import logging

logger = logging.getLogger(__name__)

def list_running_apps():
    """List all running applications.
    
    Returns:
        List of application names
    """
    apps = []
    for proc in psutil.process_iter(['name']):
        try:
            apps.append(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug(f"Could not access process info: {type(e).__name__}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error accessing process: {e}")
            continue
    return apps