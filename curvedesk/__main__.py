"""python -m curvedesk [serve|sync|report]."""
import argparse
import json
from pathlib import Path
from .data import fetch_treasury
from .service import calculation
from .server import make_server


def main():
    parser = argparse.ArgumentParser(description='CurveDesk fixed income workbench')
    parser.add_argument('command',choices=['serve','sync','report'],nargs='?',default='serve')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',default='data')
    parser.add_argument('--input',help='JSON calculation request for report command')
    parser.add_argument('--output',help='Report JSON destination')
    args = parser.parse_args()
    try:
        if args.command == 'sync':
            snap = fetch_treasury(args.data_dir)
            print(f"Saved {len(snap['records'])} Treasury observations; latest {snap['records'][-1]['date']}")
        elif args.command == 'report':
            if not args.input or not args.output:
                parser.error('report requires --input and --output')
            result = calculation(json.loads(Path(args.input).read_text(encoding='utf-8')),args.data_dir)
            Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
            print(f'Report saved to {args.output}')
        else:
            server = make_server(args.port,args.data_dir)
            print(f'CurveDesk running at http://127.0.0.1:{server.server_port} — Ctrl+C to stop',flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
    except (ValueError,OSError,KeyError) as e:
        parser.exit(1,f'Error: {e}\n')

if __name__ == '__main__':
    main()
