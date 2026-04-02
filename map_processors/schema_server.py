"""
Generates an OpenAPI 3.1 spec from GameMapStructure Pydantic models
and serves it with Scalar API reference UI.

Usage:
    python -m map_processors.schema_server [--port PORT]
"""

import argparse
import json
import logging
import re
from functools import lru_cache
from http.server import HTTPServer, SimpleHTTPRequestHandler

from map_processors.schemas import GameMapStructure

logger = logging.getLogger(__name__)


SCALAR_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tolmach — Heroes III Map Structure</title>
  <style>
    .introduction-card-item:has(.server-form) {
      display: none !important;
    }
    .sticky-cards {
      display: none !important;
    }
  </style>
</head>
<body>
  <script
    id="api-reference"
    data-url="/openapi.json"
    data-configuration='{"hiddenClients": true}'
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.25.11/dist/browser/standalone.js"></script>
</body>
</html>
"""


def _build_openapi_spec() -> dict:
    """Build an OpenAPI 3.1.0 document from GameMapStructure's JSON Schema."""
    schema = GameMapStructure.model_json_schema(mode='serialization')

    # Extract $defs and the root schema
    defs = schema.pop('$defs', {})
    components_schemas = {}

    # Put the root model itself into components
    components_schemas['GameMapStructure'] = schema

    # Hoist all $defs into components/schemas
    for name, definition in defs.items():
        components_schemas[name] = definition

    openapi = {
        'openapi': '3.1.0',
        'info': {
            'title': 'Tolmach — Heroes III Map Structure',
            'version': '0.1.0',
            'description': 'Schema for Heroes III .h3m map files as parsed by tolmach',
        },
        'paths': {
            '/map': {
                'get': {
                    'summary': 'Map structure',
                    'description': 'Complete Heroes III map structure',
                    'responses': {
                        '200': {
                            'description': 'Parsed map',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        '$ref': '#/components/schemas/GameMapStructure',
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        'components': {'schemas': components_schemas},
    }

    # Rewrite $ref paths: #/$defs/Foo -> #/components/schemas/Foo
    spec_json = json.dumps(openapi)
    spec_json = re.sub(
        r'"\#/\$defs/([^"]+)"',
        r'"#/components/schemas/\1"',
        spec_json,
    )
    return json.loads(spec_json)


@lru_cache(maxsize=1)
def _get_spec_bytes() -> bytes:
    spec = _build_openapi_spec()
    return json.dumps(spec, indent=2, ensure_ascii=False).encode()


class SchemaHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/openapi.json':
            body = _get_spec_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/':
            body = SCALAR_HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format, *args):  # noqa: A002
        logger.info('%s - %s', self.address_string(), args[0])


def main():
    parser = argparse.ArgumentParser(description='Serve Tolmach schema with Scalar UI')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    server = HTTPServer(('localhost', args.port), SchemaHandler)
    logger.info('Serving schema at http://localhost:%d', args.port)
    logger.info('OpenAPI spec at  http://localhost:%d/openapi.json', args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Shutting down.')
        server.server_close()


if __name__ == '__main__':
    main()
