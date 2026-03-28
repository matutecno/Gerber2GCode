"""Background worker thread for G-code generation."""

import sys
import traceback
import threading
from pathlib import Path
from queue import Queue

# Ensure project root is on the path so gerber2gcode is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import gerber2gcode


class GenerationWorker(threading.Thread):
    """
    Receives config dict, gbr_path, drl_paths, output_dir, queue.
    Applies config dict to a gerber2gcode.Config instance, calls gerber2gcode.run().
    Sends typed message dicts onto the queue.
    """

    def __init__(self, config: dict, gbr_path: str, drl_paths: list,
                 output_dir: str, queue: Queue, edge_path: str = None):
        super().__init__(daemon=True)
        self.config = config
        self.gbr_path = gbr_path
        self.drl_paths = drl_paths or []
        self.edge_path = edge_path or ''
        self.output_dir = output_dir
        self.queue = queue

    def run(self):
        try:
            # Build Config from dict
            cfg = gerber2gcode.Config()
            for key, value in self.config.items():
                if hasattr(cfg, key) and value is not None:
                    try:
                        setattr(cfg, key, value)
                    except Exception:
                        pass

            # Derive output path from gbr_path and output_dir
            gbr_stem = Path(self.gbr_path).stem
            output_dir = Path(self.output_dir) if self.output_dir else Path(self.gbr_path).parent.parent / "Outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"{gbr_stem}.nc")

            def progress_cb(msg):
                self.queue.put({"type": "status", "text": str(msg)})

            self.queue.put({"type": "status", "text": f"[1/4] Cargando {self.gbr_path} ..."})

            result = gerber2gcode.run(
                gbr_path=self.gbr_path,
                output_path=output_path,
                drl_paths=self.drl_paths,
                edge_path=self.edge_path or None,
                cfg=cfg,
                progress_cb=progress_cb,
            )

            # Send copper geometry for preview
            self.queue.put({
                "type": "copper",
                "geom": result['copper_geom'],
                "individuals": result['individuals'],
            })

            # Send paths for preview overlay
            self.queue.put({
                "type": "paths",
                "paths": result['paths'],
            })

            # Send drill holes and slots for preview
            if result.get('holes') or result.get('slots'):
                self.queue.put({
                    "type": "drills",
                    "holes": result.get('holes', {}),
                    "slots": result.get('slots', []),
                })

            # Done
            self.queue.put({
                "type": "done",
                "files": result['output_files'],
                "result": result,
            })

        except Exception:
            self.queue.put({
                "type": "error",
                "text": traceback.format_exc(),
            })
