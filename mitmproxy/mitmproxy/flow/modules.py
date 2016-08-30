from __future__ import absolute_import, print_function, division

import hashlib

from six.moves import urllib

from mitmproxy import controller
from netlib import wsgi
from netlib import version
from netlib import strutils
from netlib.http import http1


class AppRegistry:
    def __init__(self):
        self.apps = {}

    def add(self, app, domain, port):
        """
            Add a WSGI app to the registry, to be served for requests to the
            specified domain, on the specified port.
        """
        self.apps[(domain, port)] = wsgi.WSGIAdaptor(
            app,
            domain,
            port,
            version.MITMPROXY
        )

    def get(self, request):
        """
            Returns an WSGIAdaptor instance if request matches an app, or None.
        """
        if (request.host, request.port) in self.apps:
            return self.apps[(request.host, request.port)]
        if "host" in request.headers:
            host = request.headers["host"]
            return self.apps.get((host, request.port), None)


class StreamLargeBodies(object):
    def __init__(self, max_size):
        self.max_size = max_size

    def run(self, flow, is_request):
        r = flow.request if is_request else flow.response
        expected_size = http1.expected_http_body_size(
            flow.request, flow.response if not is_request else None
        )
        if not r.raw_content and not (0 <= expected_size <= self.max_size):
            # r.stream may already be a callable, which we want to preserve.
            r.stream = r.stream or True


class ClientPlaybackState:
    def __init__(self, flows, exit):
        self.flows, self.exit = flows, exit
        self.current = None
        self.testing = False  # Disables actual replay for testing.

    def count(self):
        return len(self.flows)

    def done(self):
        if len(self.flows) == 0 and not self.current:
            return True
        return False

    def clear(self, flow):
        """
           A request has returned in some way - if this is the one we're
           servicing, go to the next flow.
        """
        if flow is self.current:
            self.current = None

    def tick(self, master):
        if self.flows and not self.current:
            self.current = self.flows.pop(0).copy()
            if not self.testing:
                master.replay_request(self.current)
            else:
                self.current.reply = controller.DummyReply()
                master.request(self.current)
                if self.current.response:
                    master.response(self.current)


class ServerPlaybackState:
    def __init__(
            self,
            headers,
            flows,
            exit,
            nopop,
            ignore_params,
            ignore_content,
            ignore_payload_params,
            ignore_host):
        """
            headers: Case-insensitive list of request headers that should be
            included in request-response matching.
        """
        self.headers = headers
        self.exit = exit
        self.nopop = nopop
        self.ignore_params = ignore_params
        self.ignore_content = ignore_content
        self.ignore_payload_params = [strutils.always_bytes(x) for x in (ignore_payload_params or ())]
        self.ignore_host = ignore_host
        self.fmap = {}
        for i in flows:
            if i.response:
                l = self.fmap.setdefault(self._hash(i), [])
                l.append(i)

    def count(self):
        return sum(len(i) for i in self.fmap.values())

    def _hash(self, flow):
        """
            Calculates a loose hash of the flow request.
        """
        r = flow.request

        _, _, path, _, query, _ = urllib.parse.urlparse(r.url)
        queriesArray = urllib.parse.parse_qsl(query, keep_blank_values=True)

        key = [
            str(r.port),
            str(r.scheme),
            str(r.method),
            str(path),
        ]

        if not self.ignore_content:
            form_contents = r.urlencoded_form or r.multipart_form
            if self.ignore_payload_params and form_contents:
                key.extend(
                    p for p in form_contents.items(multi=True)
                    if p[0] not in self.ignore_payload_params
                )
            else:
                key.append(str(r.raw_content))

        if not self.ignore_host:
            key.append(r.host)

        filtered = []
        ignore_params = self.ignore_params or []
        for p in queriesArray:
            if p[0] not in ignore_params:
                filtered.append(p)
        for p in filtered:
            key.append(p[0])
            key.append(p[1])

        if self.headers:
            headers = []
            for i in self.headers:
                v = r.headers.get(i)
                headers.append((i, v))
            key.append(headers)
        return hashlib.sha256(repr(key).encode("utf8", "surrogateescape")).digest()

    def next_flow(self, request):
        """
            Returns the next flow object, or None if no matching flow was
            found.
        """
        l = self.fmap.get(self._hash(request))
        if not l:
            return None

        if self.nopop:
            return l[0]
        else:
            return l.pop(0)
