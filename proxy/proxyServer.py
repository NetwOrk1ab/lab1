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
        self.serverSocket.listen(config['max_connect'])
        self.pool = ThreadPoolExecutor(config['max_thread'])
        self.config = config
        self.site_config = ""
        if "site_config" in self.config:
            with open(self.config["site_config"],"r") as f:
                self.site_config = f.read()
            buffer = self.site_config
            self.siteblacklist = []
            self.userblacklist = []
            self.redirectlist = []
            for line in buffer.split("\n"):
                if line[:15]=="siteblacklist: ":
                    self.siteblacklist.append(line[15:])
                elif line[:15]=="userblacklist: ":
                    self.userblacklist.append(line[15:])
                elif line[:15]=="redirectlist : ":
                    temp = line[15:]
                    pos = temp.find("->")
                    if pos==-1:
                        continue
                    else:
                        self.redirectlist.append((temp[:pos], temp[pos+2:]))
                else:
                    continue
        #self.cacheDB = {}

    def run(self):
        while True:
            (clientSocket, client_address) = self.serverSocket.accept()
            logging.info("accept connect from "+client_address.__str__())
            #self.proxy_thread(clientSocket,client_address)
            #d = threading.Thread(target=self.proxy_thread,args=(clientSocket,client_address),daemon=True)
            #d.start()
            self.pool.submit(self.proxy_thread,clientSocket,client_address)

    def proxy_thread(self,clientsocket,clientaddress):
        ## parse the http to get host and port
        request = clientsocket.recv(self.config['max_request_len']).decode()
        filtered,newrequest = self._process(request) # filter the request.
        if filtered:
            logging.info("filter this request : "+str(clientaddress))
            clientsocket.close()
            return
        else:
            request = newrequest
        temp = self._getHost(request)
        pos = temp.find(":")
        if pos==-1:
            port = 80
            host = temp
        else :
            host = temp[:pos]
            port = int(temp[pos+1:])

        ## parse the http to get resource location
        first_line = request.split("\r\n")[0]
        resource_location = "http://"+host+":"+str(port)+first_line.split(" ")[1]
        #if self.cacheDB.has_key(resource_location):
        #    logging.info("hit a cache for "+resource_location)

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

    def _process(self,request:str)->(bool,str):
        '''
        if filter return true ,otherwise return false
        :param request: client request
        :return: return a bool,and a new request
        '''
        if self.site_config=="":
            return (False,request)
        host = self._getHost(request)
        user = self._getUser(request)
        for site in self.siteblacklist:
            if host.find(site)!=-1:
                logging.info("filter hitting "+site)
                return (True,request)
        for u in self.userblacklist:
            if user.find(u)!=-1:
                logging.info("filter hitting "+u)
                return (True,request)

        for a,b in self.redirectlist:
            if request.find(a)!=-1:
                r = request.replace(a,b)
                logging.info("redirect from "+a+" to "+b)
                return (False,r)
            else:
                continue

        return (False,request)

    def _getHost(self,request):
        '''
        this function return contains port may be
        :param request: client request
        :return: return host (may with port),if none return ""
        '''
        result = ""
        for line in request.split("\r\n"):
            if line[:6]=="Host: ":
                result = line[6:]
                break
        return result

    def _getUser(self,request):
        result = ""
        for line in request.split("\r\n"):
            if line[:12]=="User-Agent: ":
                result = line[12:]
                break
        return result
