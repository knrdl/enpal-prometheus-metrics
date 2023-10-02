import os
import socketserver
import traceback
from datetime import datetime, timezone
from http import server
from urllib.parse import urlsplit
import re

import requests
from bs4 import BeautifulSoup

box_url = os.getenv('BOX_URL', '').removesuffix('/')
assert box_url, 'Env var BOX_URL is missing, e.g. http://192.168.1.106'

box_name = os.getenv('BOX_NAME') or box_url

units = {
    'V': 'volt',
    'A': 'ampere',
    'W': 'watt',
    'Hz': 'hertz',
    'kWh': 'kwh',
    'Wh': 'wh',
    '°C': 'celsius',
    '%': 'percent'
}


def export_prometheus_metrics():
    res = requests.get(f'{box_url}/deviceMessages')
    assert res.status_code == 200, res.text

    soup = BeautifulSoup(res.text)

    output = ''

    for table in soup.find('main').findAll('table'):
        for row in table.findAll('tr'):
            if row.find('th'):
                continue
            cols = row.findAll('td')
            name, value_unit, timestamp = cols
            value_unit = (value_unit.find(text=True, recursive=False) or '').strip()

            for abbr, text in units.items():
                if value_unit.endswith(abbr):
                    value, unit = value_unit.removesuffix(abbr), text
                    break
            else:
                value, unit = value_unit, ''

            timestamp = datetime.strptime(timestamp.find(text=True, recursive=False).strip(), "%m/%d/%Y %I:%M:%S%p").replace(tzinfo=timezone.utc)
            epoch = int(timestamp.timestamp())
            name = name.text.strip().lower().replace('.', '_')
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                if m := re.fullmatch('.+\s+\((\d+)\)', value):
                    value = int(m.group(1))
            if unit:
                name += '_' + unit

            # prometheus only takes numeric values: https://github.com/prometheus/prometheus/issues/2227
            if type(value) in [float, int]:
                output += f'enpal_{name}{{box="{box_name}"}} {value} {epoch}000\n'

    return output


class HttpHandler(server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def send(self, content: str, code: int, mime: str):
        content = content.encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        try:
            url = urlsplit(self.path.strip() or '/')
            if url.path == '/metrics':
                return self.send(export_prometheus_metrics(), code=200, mime='text/plain; version=0.0.4')
            return self.send('404 not found', code=404, mime='text/plain')
        except Exception as e:
            traceback.print_exc()
            return self.send(str(e), code=500, mime='text/plain')


class HttpServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True


server = HttpServer(('', 8080), HttpHandler)
server.serve_forever()
