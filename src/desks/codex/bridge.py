"""Run the opt-in Codex app-server byte bridge until interrupted."""
import argparse
import json

from codex_bridge import Bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', default='codex')
    parser.add_argument('--auth-timeout', type=float, default=120)
    args = parser.parse_args()
    bridge = Bridge([args.codex, 'app-server', '--listen', 'stdio://'],
                    auth_timeout=args.auth_timeout).start()
    try:
        print(json.dumps(dict(port=bridge.port, token=bridge.token)), flush=True)
        while bridge.thread.is_alive():
            bridge.thread.join(1)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.close()
    if bridge.error:
        raise SystemExit(str(bridge.error))


if __name__ == '__main__':
    main()
