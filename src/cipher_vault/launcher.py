"""Native app entry point with an offline release-validation mode."""

import argparse
import json


def run():
    parser = argparse.ArgumentParser(description='Cipher Vault')
    parser.add_argument('--self-test', metavar='NEW_REPORT_PATH', help='Run synthetic runtime checks and write a JSON report without opening the UI.')
    options = parser.parse_args()
    if options.self_test:
        from .selftest import run as selftest
        from .storage import export_new
        try:
            report = selftest()
        except Exception as error:
            report = {'status': 'failed', 'error_type': type(error).__name__}
        export_new(options.self_test, json.dumps(report, indent=2).encode('utf-8'))
        if report['status'] != 'passed':
            raise SystemExit(1)
    else:
        import flet as ft
        from .app import main
        ft.run(main)
