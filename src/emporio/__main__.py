import argparse
import os

import uvicorn

from emporio.web.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Empório da Música agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()
    print(f"Amadeus: http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
