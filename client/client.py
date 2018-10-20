import socket

if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 10000))
    s.send("GET / HTTP/1.1\r\nHost: 144.34.144.4\r\n\r\n".encode())
    receive = s.recv(1000)
    print(receive.decode())
    s.close()

    # conn = http.client.HTTPConnection("127.0.0.1", 10000)
    # conn.set_tunnel("144.34.144.4")
    # conn.request("GET","/index.html",headers={"Host":"144.34.144.4"})
    # response = conn.getresponse()
    # data = response.read()
    # print (data)
    # conn.close()
