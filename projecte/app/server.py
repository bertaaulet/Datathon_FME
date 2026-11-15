#!/usr/bin/env python3
"""The tutor's web page: "Ensenya el Cangur".

    python3 app/server.py                    # on the board, then forward the port
    python3 app/server.py --host 0.0.0.0     # to open it from other devices on the network

On your laptop: adb forward tcp:8090 tcp:8090, then open http://127.0.0.1:8090

Standard library only, like the rest of the code on the board, and nothing on
the page comes from the internet. One student at a time: the model server has
one slot, and its cache holds one problem.

The page talks to copilot/tutor.py through a few JSON endpoints. The App Lab
app in applab/math-matrix reads /api/led to draw on the LED matrix.
"""
import argparse
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.client import get  # noqa: E402
from copilot.config import CONFIG, ROOT  # noqa: E402
from copilot.store import Store, default_path  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = re.compile(r"^/img/([\w.-]+\.png)$")


def is_up(port):
    try:
        return get(f"http://127.0.0.1:{port}/health", timeout=2).get("status") == "ok"
    except (OSError, ValueError):
        return False


def make_handler(tutor, images_dir):
    actions = {
        "/api/start": lambda b: tutor.start(b.get("name", ""), b.get("lang", ""),
                                            b.get("level", 0), bool(b.get("reset"))),
        "/api/next": lambda b: tutor.next(),
        "/api/practice": lambda b: tutor.next(str(b.get("id", ""))),
        "/api/answer": lambda b: tutor.answer(b.get("letter", "")),
        "/api/help": lambda b: tutor.help(),
        "/api/side-answer": lambda b: tutor.side_answer(b.get("letter", "")),
        "/api/side-reveal": lambda b: tutor.side_reveal(),
        "/api/hint": lambda b: tutor.hint(str(b.get("text", ""))[:1000]),
        "/api/leave-teaching": lambda b: tutor.leave_teaching(),
        "/api/reveal": lambda b: tutor.reveal(),
        "/api/external": lambda b: tutor.external(str(b.get("text", ""))[:4000]),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, kind="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            image = IMAGE.match(path)
            if path in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self.send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self.send(200, tutor.view())
            elif path == "/api/led":
                self.send(200, tutor.led_view())
            elif path == "/api/teacher":
                self.send(200, tutor.teacher())
            elif image and os.path.exists(os.path.join(images_dir, image.group(1))):
                with open(os.path.join(images_dir, image.group(1)), "rb") as f:
                    self.send(200, f.read(), "image/png")
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?")[0]
            if path not in actions:
                return self.send(404, {"error": "not found"})
            try:
                length = min(int(self.headers.get("Content-Length", 0)), 20000)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("expected a JSON object")
            except ValueError as error:
                return self.send(400, {"error": str(error)})
            self.send(200, actions[path](body))

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to open it to your network")
    p.add_argument("--port", type=int, default=int(CONFIG.get("TUTOR_PORT", 8090)))
    p.add_argument("--db", default=default_path())
    p.add_argument("--images", default=os.path.join(ROOT, "data", "images"))
    p.add_argument("--index", default=os.path.join(ROOT, "data", "index.db"),
                   help="retrieval index from build_index.py, to place outside problems")
    args = p.parse_args()

    os.chdir(ROOT)
    store = Store(args.db)
    usable = store.one("SELECT COUNT(*) AS n FROM problems WHERE eligible = 1")["n"]
    if not usable:
        sys.exit(f"{args.db} has no problems. Build it first: python3 prep/build_tutor_db.py")
    index = None
    if os.path.exists(args.index):
        from copilot.rag import Index
        index = Index(args.index)
    tutor = Tutor(store, index=index, images_dir=args.images)
    print(f"{usable} problems the tutor can use, languages: {', '.join(store.languages())}")
    print(f"Servers: language model {'up' if is_up(CONFIG['LLM_PORT']) else 'DOWN'}, "
          f"embeddings {'up' if is_up(CONFIG['EMBED_PORT']) else 'down'}; "
          f"outside problems {'placed with the index' if index else 'without neighbours (no index)'}")
    print(f"Open http://127.0.0.1:{args.port} (Ctrl+C to stop)")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(tutor, args.images))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
