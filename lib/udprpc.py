import socket
import json
import select

try:
    from types import FunctionType as FnType
except:
    FnType = type(lambda: 1)

    class lorem:
        def ipsum(self):
            pass

    BoundMethodType = type(lorem().ipsum)  # type = bound_method
    del lorem  # cleanup
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(name)s:%(message)s", level=logging.INFO)


class RPC:
    def __init__(self, ip="0.0.0.0", port=5001):
        logger.info(f"UDP RPC object at {ip}:{port}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((ip, port))

        self.sock = sock
        self.functions = {}

    def register(self, func):
        assert type(func) in [FnType, BoundMethodType]
        self.functions[func.__name__] = func
        logger.info(f"Registered -> {func.__name__}")
        return func

    def deregister(self, func):
        if type(func) in [FnType, BoundMethodType]:
            func = func.__name__
        elif type(func) is str:
            pass
        else:
            return False
        del self.functions[func]
        logger.info(f"Deregistered -> {func.__name__}")
        return True

    def handle(self, timeout=None):
        """timeout is the select.select timeout
        for async operation"""
        rlist, wlist, elist = [self.sock], [], []

        # block for timout seconds, when None, block indefinitely
        readable, writable, exceptional = select.select(rlist, wlist, elist, timeout)

        if self.sock not in readable:  # if sock is not readable yet, return False
            return False
        data, addr = self.sock.recvfrom(1024)
        try:
            payload = json.loads(data)
            payload["note"] = ""
        except:
            payload = {"note": "| invalid JSON format |"}
            self.sock.sendto(json.dumps(payload).encode(), addr)
            return
        finally:
            if type(payload) != dict:
                payload = {"note": "| payload must be a JSON dict |"}
                self.sock.sendto(json.dumps(payload).encode(), addr)
                return

        if not "method" in payload:
            payload["note"] += "| missing JSON key 'method' |"
            method = ""
        else:
            method = payload["method"]
            # del payload["method"]

        if not "params" in payload:
            params = []
            payload["note"] += "| Warning: missing JSON key 'params' |"
        else:
            params = payload["params"]
            # del payload["params"]

        if not type(params) == list:
            payload["note"] += "| 'params' key in JSON is not a list |"

        if method == "":
            pass
        elif not method in self.functions:
            payload["note"] += "| method not found in registry |"
        else:
            try:
                payload["result"] = self.functions[method](*params)
            except:
                payload["note"] += f"| Exception calling {method}(*{params}) |"
                __fn = self.functions[method]
                if "__doc__" in dir(__fn):
                    payload["fndoc"] = __fn.__doc__

        # write results back
        self.sock.sendto(json.dumps(payload).encode(), addr)

    def close(self):
        self.sock.close()

    def __del__(self):
        self.close()


if __name__ == "__main__":
    rpc = RPC()

    @rpc.register
    def listall():
        """lists all rpcs that are registered"""
        return list(rpc.functions)

    @rpc.register
    def help(fn: str):
        """returns the doc string"""
        if fn in rpc.functions:
            fn = rpc.functions[fn]
            return fn.__doc__

    while True:
        rpc.handle()
