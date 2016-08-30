from __future__ import absolute_import, print_function, division
import os.path

from mitmproxy import exceptions
from mitmproxy.flow import io


class FileStreamer:
    def __init__(self):
        self.stream = None
        self.active_flows = set()  # type: Set[models.Flow]

    def start_stream_to_path(self, path, mode, filt):
        path = os.path.expanduser(path)
        try:
            f = open(path, mode)
        except IOError as v:
            return str(v)
        self.stream = io.FilteredFlowWriter(f, filt)
        self.active_flows = set()

    def configure(self, options, updated):
        # We're already streaming - stop the previous stream and restart
        if self.stream:
            self.done()

        if options.outfile:
            filt = None
            if options.get("filtstr"):
                filt = filt.parse(options.filtstr)
                if not filt:
                    raise exceptions.OptionsError(
                        "Invalid filter specification: %s" % options.filtstr
                    )
            path, mode = options.outfile
            if mode not in ("wb", "ab"):
                raise exceptions.OptionsError("Invalid mode.")
            err = self.start_stream_to_path(path, mode, filt)
            if err:
                raise exceptions.OptionsError(err)

    def tcp_open(self, flow):
        if self.stream:
            self.active_flows.add(flow)

    def tcp_close(self, flow):
        if self.stream:
            self.stream.add(flow)
            self.active_flows.discard(flow)

    def response(self, flow):
        if self.stream:
            self.stream.add(flow)
            self.active_flows.discard(flow)

    def request(self, flow):
        if self.stream:
            self.active_flows.add(flow)

    def done(self):
        if self.stream:
            for flow in self.active_flows:
                self.stream.add(flow)
            self.active_flows = set([])
            self.stream.fo.close()
            self.stream = None
