import threading
import socket
import signal
import logging
from concurrent.futures import ThreadPoolExecutor

class proxyServer:
    def __init__(self,config):
        logging.basicConfig(level=logging.INFO)
        #signal.signal(signal.SIGINT,self.shutdown)
        self.serverSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        # self.serverSocket.setsockopt()
        self.serverSocket.bind((config['host_name'],config['bind_port']))
        logging.info("bind proxy host:"+config['host_name']+" port:"+str(config['bind_port']))
        self.serverSocket.listen(10)
        self.pool = ThreadPoolExecutor(10)
        self.config = config

    def run(self):
        while True:
            (clientSocket, client_address) = self.serverSocket.accept()
            logging.info("accept connect from "+client_address.__str__())
            #self.proxy_thread(clientSocket,client_address)
            #d = threading.Thread(target=self.proxy_thread,args=(clientSocket,client_address),daemon=True)
            #d.start()
            self.pool.submit(self.proxy_thread,clientSocket,client_address)

    def proxy_thread(self,clientsocket,clientaddress):
        ## parse the http
        request = clientsocket.recv(self.config['max_request_len']).decode()
        for line in request.split("\r\n"):
            if line[:6]=="Host: ":
                temp = line[6:]
                break
        pos = temp.find(":")
        if pos==-1:
            port = 80
            host = temp
        else :
            host = temp[:pos]
            port = int(temp[pos+1:])
        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        s.settimeout(self.config['timeout'])
        logging.info("try to connect dst address "+(host,port).__str__())
        try:
            s.connect((host,port))
        except TimeoutError:
            logging.info("fail to connect "+(host,port).__str__())
            return
        s.send(request.encode())
        while True:
            data = s.recv(self.config['max_request_len'])
            if len(data)>0:
                clientsocket.send(data)
            else:
                break
        clientsocket.close()
        s.close()



