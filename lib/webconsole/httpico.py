import json, logging
from socket import socket, SOCK_STREAM, AF_INET, SOL_SOCKET, SO_REUSEADDR


class Request:
    def __init__(self):
        pass

    def __call__(self, rawhttp):
        header_end = rawhttp.index("\r\n")  # first index of "\n\n"
        head, self.body = rawhttp[:header_end], rawhttp[header_end:]

        head = head.split("\r\n")
        self.method, self.rawpath, self.version = head.pop(0).strip().split(" ")
        self.headers = {}
        for h in head:
            key, val = h.strip().split(":")
            self.headers[key] = val

        # extract GET parameters if there is one
        route = self.rawpath.split("?")
        if len(route) > 1:  # check if we have get params
            get_params = route[1]
            # parse GET params
            self.query = {}
            for q in get_params.split("&"):
                qkey, qval = q.split("=")
                self.query[qkey] = qval

        self.route = route[0]


class Response:
    def __init__(self):
        self.statustext = {200: "OK", 404: "Not Found"}
        self.contenttype = {str: "text/html; charset=UTF-8", dict: "application/json"}

    def __call__(self, body, request, statuscode=200, headers={}):
        # prepare body
        bodytype = type(body)
        body = (
            body if bodytype in [str, dict] else str(body)
        )  # to str if not str/dict(json)
        body = json.dumps(body) if bodytype is dict else body  # to json if a dict

        # set headers
        header = {"Content-Type": self.contenttype[bodytype]}
        header.update({"Content-Length": len(body)})
        header.update(headers)  # custom headers, will override above ones if present

        header = "\r\n".join([f"{k}: {v}" for k, v in header.items()])

        header0 = [f"{request.version} {statuscode} {self.statustext[statuscode]}"]
        header = f"{header0}\r\n{header}\r\n"

        # return response
        response = f"{header}\r\n{body}"
        return response


class HTTPico:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # reuse

        # handlers registry
        self.gets = {}
        self.posts = {}

        # Req parser and Resp generator
        self.request = Request()
        self.response = Response()

        # logger
        self.logger = logging.getLogger(__name__)

    def start(self, timeout=None, conn_queue_size=7):
        self.sock.bind((self.host, self.port))
        self.sock.listen(conn_queue_size)
        # at max 7 connections can be waiting in the backlog queue
        # while we are processing and responding to the current one

    def serve(self, rcvbufsize=2048):
        try:
            clientsock, clientaddr = self.sock.accept()
            rawreq = clientsock.recv(
                rcvbufsize
            ).decode()  # request should be within these no. of bytes

            req = self.request
            req(rawreq)

            if req.method == "GET":
                if req.route not in self.gets:
                    rawresp = ""
                    statuscode = 404  # not found
                else:
                    cb = self.gets[req.route]
                    argnames = cb.__code__.co_varnames
                    kwargs = {}
                    for arg in argnames:
                        val = req.query[arg] if arg in req.query else None
                    rawresp = cb(**kwargs)
                    statuscode = 200

                resp = self.response(rawresp, req, statuscode)

            elif req.method == "POST":
                pass

            clientsock.sendall(resp.encode())

            # log
            self.logger.info(f"{req.method} {req.rawpath} {req.version}  {statuscode}")

        except KeyboardInterrupt:
            raise
        finally:
            clientsock.close()

    def get(self, path):
        def wrapper(cb):
            self.gets[path] = cb

        return wrapper

    def post(self, path):
        def wrapper(cb):
            self.posts[path] = cb

        return wrapper


if __name__ == "__main__":
    # print(rawhttp.encode());

    # set logging level
    logging.basicConfig(level=logging.INFO)

    HOST, PORT = "localhost", 2345

    app = HTTPico(HOST, PORT)

    @app.get("/")
    def g():
        return open("templates/index.html").read()

    @app.post("/get")
    def p():
        return {"hare": "krishna"}

    app.start()

    app.logger.info(f"Serving at {HOST}:{PORT}")

    for i in range(10):
        app.serve()
