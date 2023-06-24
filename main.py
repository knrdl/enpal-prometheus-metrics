import ipaddress
import os
import socketserver
import traceback
from datetime import datetime, timezone
from http import server
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

box_ip = os.getenv('BOX_IP')
assert box_ip, 'Env var BOX_IP is missing'
assert ipaddress.ip_address(box_ip)

def export_prometheus_metrics():
    res = requests.get(f'http://{box_ip}/deviceMessages')
    assert res.status_code == 200, res.text

    soup = BeautifulSoup(res.text)

    output = ''

    for table in soup.find('main').findAll('table'):
        for row in table.findAll('tr'):
            timestamp, name, value, unit = row.findAll('td')
            timestamp = int(datetime.strptime(timestamp.text, "%m/%d/%Y %I:%M:%S%p").replace(tzinfo=timezone.utc).timestamp())
            name = name.text.strip().lower().replace('.', '_')
            try:
                if '.' in value.text:
                    value = float(value.text)
                else:
                    value = int(value.text)
            except ValueError:
                value = value.text.strip()
            unit = unit.text.strip().lower()
            if unit:
                unit = {'v': 'volt', 'a': 'ampere', 'w': 'watt', 'hz': 'hertz'}.get(unit, unit)
                name += '_' + unit

            if type(value) in [float, int]:  # prometheus only takes numeric values: https://github.com/prometheus/prometheus/issues/2227
                output += f'enpal_{name}{{box_ip="{box_ip}"}} {value} {timestamp}000\n'

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
