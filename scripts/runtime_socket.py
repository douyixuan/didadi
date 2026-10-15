"""Start the development WebSocket bridge; no public binding is supported."""
import argparse
from pathlib import Path
from src.runtime_socket import bridge

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:9000')
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--port', type=int, default=9020)
    args = parser.parse_args()
    with bridge(args.url, Path(args.token_file).read_text().strip(), args.port) as server:
        server.serve_forever()
