from fire import Fire
from socket import SOCK_DGRAM, AF_INET, socket
from json import dumps, loads



def main(host="localhost", port=5001, method="listall", params=[]):
    if type(params) not in [list,tuple]:
        params = [params]  # params must always be a list

    # print(method)
    # print(params)

    payload = dumps({"method": method, "params": params})

    sock = socket(AF_INET, SOCK_DGRAM) # open socket
    sock.sendto(payload.encode(), (host, port))
    data, server = sock.recvfrom(1024)
    data = dumps(loads(data), indent=2)
    print(data)

    sock.close() # close socket

if __name__ == "__main__":
    Fire(main)
