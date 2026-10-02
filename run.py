"""Quick launcher for S.A.R.A.

Usage:
    python run.py           # starts the server on http://0.0.0.0:8000
    python run.py --port 8080
"""
import argparse
import os
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch S.A.R.A AI assistant")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[os.path.join(os.path.dirname(__file__), "backend"),
                     os.path.join(os.path.dirname(__file__), "frontend")] if args.reload else None,
    )


if __name__ == "__main__":
    main()
