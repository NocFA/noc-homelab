import platform

def get_platform_handler():
    """Get the appropriate platform handler for the current OS."""
    system = platform.system().lower()

    if system == 'darwin':
        from .darwin import DarwinHandler
        return DarwinHandler()
    elif system == 'windows':
        from .windows import WindowsHandler
        return WindowsHandler()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
