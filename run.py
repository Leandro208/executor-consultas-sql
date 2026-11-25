"""Ponto de entrada da aplicacao.

Uso:
    python run.py            # sobe em 127.0.0.1:5000
    python run.py --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse

from app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Executor de Consultas SQL")
    parser.add_argument("--host", default=None, help="Interface de rede (padrao 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Porta (padrao 5000)")
    parser.add_argument("--debug", action="store_true", help="Ativa modo debug")
    args = parser.parse_args()

    app = create_app()
    host = args.host or app.config["EXECUTOR_HOST"]
    port = args.port or app.config["EXECUTOR_PORT"]

    print(f"Executor de Consultas SQL em http://{host}:{port}")
    app.run(host=host, port=port, debug=args.debug)


if __name__ == "__main__":
    main()
