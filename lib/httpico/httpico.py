import os, sys, json, logging
from socket import socket, SOCK_STREAM, AF_INET, SOL_SOCKET, SO_REUSEADDR
from datetime import datetime as dtime
from types import NoneType


class Request:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.headers = {}
        self.method = None
        self.rawpath = None
        self.version = None
        self.body = ""

    def __call__(self, rawhttp):
        if "\r\n\r\n" in rawhttp:
            header_end = rawhttp.index("\r\n\r\n")  # first index of "\r\n\r\n"
        else:
            return
        head, self.body = rawhttp[:header_end], rawhttp[header_end + 4 :]
        head = head.split("\r\n")
        self.method, self.rawpath, self.version = head.pop(0).strip().split(" ")
        self.headers = {}
        for h in head:
            first_colon_index = h.index(":")
            key, val = h[:first_colon_index], h[first_colon_index + 1 :].strip()
            self.headers[key] = val
        
        del head # strings are immutable in python, so we free up the space after extraction.
        
        # url_decode the rawpath as it must have url_encoded any special character.
        self.rawpath = self.url_decode(self.rawpath)

        # extract GET parameters if there is one
        route = self.rawpath.split("?")
        if len(route) > 1:  # check if we have get params
            get_params = route[1]
            # parse GET params
            self.query = {}
            try:
                for q in get_params.split("&"):
                    qkey, qval = q.split("=")
                    self.query[qkey] = qval
            except:
                self.logger.info(
                    "Failed to parse query fields from get_params in the URL !"
                )
        self.route = route[0]

        # extract paramters/data from POST
        if self.method == "POST" and (int(self.headers["Content-Length"]) > 0):
            # variables to be expected when handling a POST request.
            self.form = {}

            if (
                self.headers["Content-Type"] == "application/x-www-form-urlencoded"
            ) and (int(self.headers["Content-Length"].split(":")) > 0):
                # parse FROM params
                for q in self.body.split("&"):
                    qkey, qval = q.split("=")
                    self.form[qkey] = qval

            elif "multipart/form-data" in (conttype := self.headers["Content-Type"]):
                # check if has boundaries
                boundary = None
                cnts = conttype.split(f";")
                for cnt in cnts:
                    if "boundary" in cnt:
                        boundary = cnt.split("=")[1]
                
                if boundary != None:
                    end_boundary_removed_body = self.body.split(f"--{boundary}--")[0]
                    dataparts = end_boundary_removed_body.split(f"--{boundary}\r\n")
                    for datapt in dataparts:
                        if not "\r\n\r\n" in datapt:
                            continue
                        __headers, payload = datapt.split("\r\n\r\n")  # headers and
                        #payload = payload[
                        #    :-2
                        #]  # the last two bytes are \r\n and are not part of the payload
                        for head in __headers.split("\r\n"):
                            if head.startswith("Content-Disposition:"):
                                cdispositions = head[len("Content-Disposition:") :]
                                if "form-data" in cdispositions:
                                    # Content-Disposition: form-data; name="filedir"
                                    for cdisp_part in cdispositions.split(";"):
                                        if (
                                            "name=" in cdisp_part
                                        ):  # this handles both name=.. and filename=... | a problem with this is if someone is sending a variable named "filename" itself bnut we let it be for now.
                                            if "filename=" in cdisp_part:
                                                filename = cdisp_part.split("=")[
                                                    -1
                                                ]  # has surrounding double quotes
                                                filename = filename[
                                                    1:-1
                                                ]  # remove the double quotes filename
                                                self.form["filename"] = filename
                                            else:
                                                varname = cdisp_part.split("=")[
                                                    1
                                                ]  # varname = '"variable_name"'
                                                varname = varname[
                                                    1:-1
                                                ]  # varname = 'variable_name'
                                                self.form[varname] = payload

    def url_decode(self, url):
        # this function was generated by chatgpt
        i = 0
        decoded = ""
        while i < len(url):
            if url[i] == "%":  # Check for percent-encoded character
                hex_value = url[i + 1 : i + 3]  # Get the next two characters
                decoded += chr(int(hex_value, 16))  # Convert hex to ASCII
                i += 3  # Move past the percent and two hex characters
            elif url[i] == "+":  # Decode '+' as space
                decoded += " "
                i += 1
            else:
                decoded += url[i]  # Add regular character
                i += 1
        return decoded


class Response:
    def __init__(self):
        self.statustext = {
            200: "OK",
            201: "Created",
            202: "Accepted",  # used for successful delete
            204: "No Content",  # delete sucessful but no content/body will be returned
            404: "Not Found",
            400: "Bad Request",
            500: "Internal Server Error",
        }
        self.contenttype = {
            NoneType: "text/html; charset=UTF-8",
            str: "text/html; charset=UTF-8",
            dict: "application/json",
        }
        self.statuscode = 0  # inital val

    def __call__(self, body, request, statuscode=200, headers={}):
        # prepare body
        bodytype = type(body)
        body = (
            body if bodytype in [str, dict] else str(body)
        )  # to str if not str/dict(json)
        body = json.dumps(body) if bodytype is dict else body  # to json if a dict

        # if body == None, then just fill statuscode with 404/400 for GET/POST
        if bodytype == NoneType:
            if request.method == "GET":
                statuscode = 404  # not found
            elif request.method == "POST":
                statuscode = 400  # Bad request

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
    def __init__(self, host, port, fbroot=None, fbroute=""):
        """
        enable filebrowser with root at fbroot
        fbroot cannot start with a dot relative path
        valid examples: lorem/ipsum, /home/lorem/ipsum
        invalid examples: ./lorem, ./lorem/ipsum

        fbroute is the webroot where the file browser will lie w.r.t
        the web domain.
        """
        self.host = host
        self.port = port
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # reuse

        # handlers registry
        self.gets = {}
        self.posts = {}
        self.puts = {}
        self.deletes = {}

        # Req parser and Resp generator
        self.request = Request()
        self.response = Response()

        # logger
        self.logger = logging.getLogger(__name__)

        if fbroot != None:
            assert not fbroot.startswith(
                "."
            ), "fbroot cannot be a dot relative path, i.e it cannot start with a dot(.)"
            assert fbroot.endswith("/"), "fbroot must end with forward slash(/)"
        self.fbroot = fbroot
        if fbroute != "":
            assert fbroute.endswith("/"), "fbroute must end with forward slash(/)"

        self.fbroute = (
            fbroute if fbroute.startswith("/") else f"/{fbroute}"
        )  # has to start with / as the url part of the http request starts with /

    def start(self, timeout=None, conn_queue_size=7):
        self.sock.bind((self.host, self.port))
        self.sock.listen(conn_queue_size)
        # at max 7 connections can be waiting in the backlog queue
        # while we are processing and responding to the current one

    def serve(self, rcvbufsize=4096):
        clientsock, clientaddr = self.sock.accept()
        try:
            rawreq = clientsock.recv(
                rcvbufsize
            ).decode()  # request should be within these no. of bytes

            req = self.request
            req(rawreq)

            if req.method == "OPTIONS":  # for AJAX preflight
                # allow all methods from all urls
                opt_response = """
                HTTP/1.1 204 No Content
                Access-Control-Allow-Origin: *
                Access-Control-Allow-Methods: GET, POST, OPTIONS, PUT, DELETE
                Access-Control-Allow-Headers: Content-Type
                """
                clientsock.sendall(opt_response)

            elif req.method == "GET":
                # registered gets
                if req.route in self.gets:
                    stscode = 200
                    cb = self.gets[req.route]
                    argnames = cb.__code__.co_varnames[: cb.__code__.co_argcount]
                    kwargs = {}
                    for arg in argnames:
                        kwargs[arg] = req.query[arg] if arg in req.query else None
                    rawresp = cb(**kwargs)
                    if len(rawresp) > 1:
                        stscode, rawresp = rawresp
                    resp = self.response(rawresp, req, statuscode=stscode)
                    clientsock.sendall(resp.encode())  # send the response

                # serve files (if starts with fbroute)
                elif (rawresp := self.filebrowse(req.route, method=req.method)) != (
                    None,
                    None,
                ):
                    stscode = 200
                    filesize, chunked_fileread_generator = rawresp
                    resp = self.response(
                        body="",
                        request=req,
                        statuscode=stscode,
                        headers={"Content-Length": filesize},
                    )
                    clientsock.sendall(resp.encode())  # send headers
                    for chunk in chunked_fileread_generator:  # send the body in chunks to not overflow the RAM as the files could be really large to directly load to RAM
                        clientsock.sendall(chunk.encode())

                # not found
                else:
                    stscode = 404
                    rawresp = f"{stscode} | NOT FOUND !!!"
                    resp = self.response(rawresp, req, stscode)
                    clientsock.sendall(resp.encode())

            # HANDLE POSTs
            elif req.method == "POST":
                if req.route in self.posts:
                    stscode = 201
                    cb = self.posts[req.route]
                    argnames = cb.__code__.co_varnames[
                        : cb.__code__.co_argcount
                    ]  # get names of arguments
                    kwargs = {}
                    for arg in argnames:
                        kwargs[arg] = req.form[arg] if arg in req.form else None
                    rawresp = cb(**kwargs)
                    if len(rawresp) > 1:
                        stscode, rawresp = rawresp
                    resp = self.response(rawresp, req, statuscode=stscode)
                    clientsock.sendall(resp.encode())  # send the response

                # write/save files (if starts with fbroute)
                elif (rawresp := self.filebrowse(req.route, method=req.method)) != (
                    None,
                    None,
                ):
                    stscode = 200
                    filesize, chunked_fileread_generator = rawresp
                    resp = self.response(
                        body="",
                        request=req,
                        statuscode=stscode,
                        headers={"Content-Length": filesize},
                    )
                    clientsock.sendall(resp.encode())  # send headers

                else:
                    stscode = 400
                    rawresp = f"{stscode} | BAD REQUEST !!!"
                    resp = self.response(rawresp, req, stscode)
                    clientsock.sendall(resp.encode())

            # handle new folder creation
            elif req.method == "PUT":
                if req.route in self.puts:
                    stscode = 200
                    cb = self.puts[req.route]
                    argnames = cb.__code__.co_varnames[
                        : cb.__code__.co_argcount
                    ]  # get names of arguments
                    kwargs = {}
                    for arg in argnames:
                        kwargs[arg] = req.form[arg] if arg in req.form else None
                    rawresp = cb(**kwargs)
                    if len(rawresp) > 1:
                        stscode, rawresp = rawresp
                    resp = self.response(rawresp, req, statuscode=stscode)
                    clientsock.sendall(resp.encode())  # send the response

                # mkdir (if starts with fbroute)
                elif (rawresp := self.filebrowse(req.route, method=req.method)) != (
                    None,
                    None,
                ):
                    stscode, body = rawresp
                    resp = self.response(
                        body=body,
                        request=req,
                        statuscode=stscode,
                    )
                    clientsock.sendall(resp.encode())  # send headers

            # handle delete file in filebrowser
            elif req.method == "DELETE":
                if req.route in self.deletes:
                    stscode = 200
                    cb = self.deletes[req.route]
                    argnames = cb.__code__.co_varnames[
                        : cb.__code__.co_argcount
                    ]  # get names of arguments
                    kwargs = {}
                    for arg in arcgnames:
                        kwargs[arg] = req.form[arg] if arg in req.form else None
                    rawresp = cb(**kwargs)
                    if len(rawresp) > 1:
                        stscode, rawresp = rawresp
                    resp = self.response(rawresp, req, statuscode=stscode)
                    clientsock.sendall(resp.encode())  # send the response

                elif (rawresp := self.filebrowse(req.route, method=req.method)) != (
                    None,
                    None,
                ):
                    stscode, rawresp = rawresp
                    resp = self.response(rawresp, req, statuscode=stscode)
                    clientsock.sendall(resp.encode())  # send the response

                else:
                    stscode = 400
                    rawresp = f"{stscode} | BAD REQUEST !!!"
                    resp = self.response(rawresp, req, stscode)
                    clientsock.sendall(resp.encode())

            # log
            self.logger.info(
                f"{req.method:<4} {req.rawpath:<50} {req.version:<8}    {stscode}"
            )

        except Exception as e:
            raise
            self.logger.info(f"Exception: {e}")
        finally:
            clientsock.close()

    def stop(self):
        self.sock.close()

    def get(self, path):
        def wrapper(cb):
            self.gets[path] = cb

        return wrapper

    def post(self, path):
        def wrapper(cb):
            self.posts[path] = cb

        return wrapper

    def delete(self, path):
        def wrapper(cb):
            self.deletes[path] = cb

        return wrapper

    def filebrowse(self, route, method):
        if self.fbroot == None:  # if fbrowser not enabled, return None immediately
            return None, None
        if not route.startswith(self.fbroute):  # not to be handled by filebrowser
            return None, None
        else:
            self.logger.error(self.fbroot)
            self.logger.error(self.fbroute)
            self.logger.error(route)
            fspath = os.path.join(
                self.fbroot, route[len(self.fbroute) :]
            )  # fbroute must end with /
            self.logger.error(fspath)

        # HANDLE GET
        if method == "GET" and os.path.isfile(fspath):
            # return generator
            def fread_chunked():
                with open(fspath, "r") as f:
                    while chunk := f.read(2048):  # default chunk size of 2048
                        yield chunk

            return os.path.getsize(fspath), fread_chunked()

        elif method == "GET" and os.path.isdir(fspath):
            children = os.listdir(fspath)
            children = [(child, os.path.join(fspath, child)) for child in children]
            # append forward slash (/) if a directory by using os.path.join("hello","")
            # to make it "hello/"
            children = [
                (
                    os.path.join(child, "") if os.path.isdir(childpath) else child,
                    childpath,
                )
                for child, childpath in children
            ]

            # body
            html = f"""
                    <body>
                    <h2>HTTPico File Browser</h2>
                    <h3>pwd: <u>{fspath}</u><input type="text" id="newfoldername"></input> &nbsp;&nbsp<button id="createfolder" onclick="mkdir(document.getElementById('newfoldername').value)">Create Folder</button></h3>
                    
                    </br>
                    <form action="/upload" method="post" enctype="multipart/form-data">
                       <label for="files">Upload:</label> 
                        <input name="filecontent" type="file" accept="*" required></input>
                        <input name="filedir" type="text" value="{fspath}"></input>
                        <input type="submit"></input>
                    </form></br></br>"""

            # file table
            html += f"""<table>
                    <thead>
                        <tr>
                            <th>Size</th>
                            <th>Last Modified</th>
                            <th>Name</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tr>
                        <td></td>
                        <td></td>
                        <td> <a style="color:forestgreen" href="{os.path.dirname(route[:-1] if route.endswith("/") else route )}/">..</a> </td>
                        <td></td>
                    </tr>
                    """

            tablerows = "\n".join(
                [
                    """<tr>
                    <td>{filesize}</td>
                    <td>{modtime}</td>
                    <td>
                        <a style="color: {childcolor};" href="{childname}">{childname}</a>
                    </td>
                    <td>
                        <button onclick="deletefile('{childname}')">delete</button>
                    </td>
                    </tr>""".format(
                        filesize="---"
                        if os.path.isdir(childpath)
                        else os.path.getsize(childpath)
                        if os.path.getsize(childpath) < 1024
                        else f"{(os.path.getsize(childpath)/1024):.1f}k",
                        # childroute=os.path.join(route, childname),
                        childname=childname,
                        childpath=childpath,
                        childcolor="springgreen"
                        if os.path.isdir(childpath)
                        else "magenta",
                        modtime=dtime.fromtimestamp(
                            os.path.getmtime(childpath)
                        ).strftime("%d %b %H:%M"),
                    )
                    for childname, childpath in children
                ]
            )

            html += "<tbody>\n" + tablerows + "\n</tbody>\n</table>"

            # add css
            html += """
            <style>
            body{
                background: black;
                font-family: monospace
            }
            h2{
                color: indianred;
            }
            h3{
                color: gold;
            }
            table {
              width: 50%;
              border-collapse: collapse; /* Remove double borders */
              text-align: left; /* Align text to the left */
              /* font-family: monospace;*/ /* Clean font */
              font-size: 16px; /* Legible size */
            }

            th, td {
              /*padding: 10px; *//* Equal spacing */
              /* border: 1px solid #ddd; *//* Light border */
              color: gray;
            }

            thead {
              font-weight: bold;
              font-style: italic;
            }

            form label{ "fbrout must end with forward slash(/)"
                color: deepskyblue;
                font-weight: bold;
                font-size: 1.25em;
                text-decoration: underline;
                margin-right: 1em;
            }
            form input::file-selector-button{
                background: lightSteelBlue;
            }
            form input[type=file]{
                color: deepskyblue;
                font-style: italic;
                font-weight: bold;
            }
            form input[type=submit]{
                background: lightSteelBlue
            }
            
            #createfolder, #newfoldername{
                border-radius: 1em;
                background: silver;
                
            }
            </style>

            <script>
                function deletefile(filename){
                if(!confirm("Delete file: " + filename + "! Sure?")) return;
                fetch(url=filename, {method: 'DELETE'}).then(response => response.json()).then(data=>{console.log(data);if(data.status==0)window.location.reload(true)});
                }


                function mkdir(foldername){
                    if(foldername=="") return;
                    if(foldername.includes("/") | foldername.includes(".")) {
                        alert("'/' and '.' cannot be part of the folder name");
                        return;
                    }
                    //confirm("Create new folder? Name: " + foldername )
                    fetch(url=foldername, {method: "PUT"}).then(response => response.json()).then(data => {console.log(data); if(data.status==0)window.location.reload(true)})
                }
            </script>
            """
            # return html
            return len(html), (
                h for h in [html]
            )  # mimic filesize, chunked read generator

        # path not found - neither a file nor a directory
        elif method == "GET":
            return None, None

        # Handle upload
        elif method == "POST":
            self.logger.error(fspath)
            self.logger.error(req.form)

        elif method == "PUT":
            # since the newfoldername(the last part of fspath after /),
            # and as it may contain special characters( as it was input by user),
            # the fetch request would have url_encoded the special characters,
            # hence we need to url_decode it.
            # fspath = self.url_decode(fspath)

            newdir = os.path.join(fspath)
            os.mkdir(newdir)
            return 201, {"status": 0, "info": f"created folder: {newdir}"}

        # HANDLE DELETE
        elif method == "DELETE":
            # fetch will url_encode the special characters in the file/foldername,
            # and since the file/foldername is part of the url when fetch is sent,
            # and that the url is now part of fspath, we need to url_decode it
            # fspath = self.url_decode(fspath)
            if os.path.isdir(fspath):
                if len(os.listdir(fspath)) == 0:
                    os.rmdir(fspath)
                    return 200, {"status": 0, "info": f"deleted folder{fspath}"}
                else:
                    return 400, {"status": 1, "info": f"failed! Directory not empty."}
            elif os.path.isfile(fspath):
                os.remove(fspath)
                return 200, {"status": 0, "info": f"deleted file{fspath}"}
            else:
                return 400, {"status": 2, "info": f"failed to delete: {fspath}"}


def fileuploader(filedir, filename, filecontent):
    if type(filedir) == type(filename) == type(filecontent) == str:
        pass
    else:
        return None

    fspath = os.path.join(filedir, filename)
    if os.path.exists(fspath):
        return 400, {"status": 1, "info": f"file:{fspath} already exists !!!"}
    else:
        try:
            with open(fspath, "w") as g:
                g.write(filecontent)
            return 201, {
                "status": 0,
                "info": f"Succesfully wrote {len(filecontent)} bytes into: {fspath}",
            }
        except Exception as e:
            return 500, {"status": 2, "info": f"Internal Server Exception -> {e}"}


if __name__ == "__main__":
    # print(rawhttp.encode());

    # set logging level
    logging.basicConfig(level=logging.INFO)

    HOST, PORT = "localhost", 2345

    app = HTTPico(HOST, PORT, fbroot="templates/", fbroute="files/")

    @app.get("/")
    def g():
        return open("templates/index.html").read()

    # file upload
    app.post("/upload")(fileuploader)

    app.start()

    app.logger.info(f"Serving at {HOST}:{PORT}")

    for i in range(10):
        app.serve()
