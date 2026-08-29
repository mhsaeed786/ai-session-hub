"""Fix NovelForge __init__ with the REAL class names."""
import os
import subprocess

NF = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge"
init_path = os.path.join(NF, "novel_forge", "__init__.py")

REAL_CLASSES = ["GenrePreset", "PlotStructureConfig", "ProseStyleConfig",
                "ToneConfig", "ResearchDepthConfig"]

init = """\"\"\"NovelForge - AI-powered novel generation system.\"\"\"

from .core.config import (
    GenrePreset,
    PlotStructureConfig,
    ProseStyleConfig,
    ToneConfig,
    ResearchDepthConfig,
)

# Backward-compat aliases (original names from earlier versions)
NovelConfig = PlotStructureConfig
Genre = GenrePreset
ProseStyle = ProseStyleConfig
PlotStructure = PlotStructureConfig

__all__ = [
    "GenrePreset", "PlotStructureConfig", "ProseStyleConfig",
    "ToneConfig", "ResearchDepthConfig",
    "NovelConfig", "Genre", "ProseStyle", "PlotStructure",
]
"""

with open(init_path, "w", encoding="utf-8", newline="") as f:
    f.write(init)
print("wrote clean __init__.py")


def run(cmd, cwd=None, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, shell=True)


vpy = os.path.join(NF, "venv", "Scripts", "python.exe")

r = run(f'"{vpy}" -c "import sys; sys.path.insert(0,\'.\'); '
        f'import novel_forge; print(\'pkg OK\')"', cwd=NF)
print("package:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-300:].replace(chr(10), " | "))

r2 = run(f'"{vpy}" -c "import sys; sys.path.insert(0,\'.\'); '
         f'from novel_forge.output import exporter; print(\'exporter OK\')"',
         cwd=NF)
print("exporter:", "PASS" if r2.returncode == 0 else
      (r2.stderr or "")[-300:].replace(chr(10), " | "))
