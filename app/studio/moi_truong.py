"""Keep processes in the environment selected by the external Studio launcher."""
import os
import sys


def python_da_chon():
    """Return only an explicitly selected interpreter from the running venv.

    An invalid selection is an error, rather than a reason to launch the legacy
    environment or an arbitrary executable supplied in an environment variable.
    """
    selected = os.environ.get("STUDIO_PYTHON")
    if not selected:
        return None
    if not os.path.isabs(selected):
        raise RuntimeError("STUDIO_PYTHON phải là đường dẫn tuyệt đối của môi trường đang chạy.")
    selected = os.path.abspath(selected)
    current = os.path.abspath(sys.executable)
    same = os.path.normcase(selected) == os.path.normcase(current)
    same_windows_pair = (
        os.name == "nt"
        and os.path.normcase(os.path.dirname(selected)) == os.path.normcase(os.path.dirname(current))
        and os.path.basename(selected).lower() == "python.exe"
        and os.path.basename(current).lower() == "pythonw.exe"
    )
    venv = os.path.dirname(os.path.dirname(selected))
    if (not (same or same_windows_pair)
            or os.path.normcase(venv) != os.path.normcase(os.path.abspath(sys.prefix))
            or not os.path.isfile(selected)
            or not os.path.isfile(os.path.join(venv, "pyvenv.cfg"))):
        raise RuntimeError("Python đang chạy không khớp môi trường đã chọn; hãy mở lại Studio bằng start.bat.")
    return selected
