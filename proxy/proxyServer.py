import logging
import socket
from concurrent.futures import ThreadPoolExecutor

import cacheout


class proxyServer:
    def __init__(self, config):
        logging.basicConfig(level=logging.INFO)
        # signal.signal(signal.SIGINT,self.shutdown)
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.serverSocket.setsockopt()
        self.serverSocket.bind((config['host_name'], config['bind_port']))
        logging.info("bind proxy host:" + config['host_name'] + " port:" + str(config['bind_port']))
        self.serverSocket.listen(config['max_connect'])
        self.pool = ThreadPoolExecutor(config['max_thread'])
        self.config = config
        self.site_config = ""
        if self.config["cache"]:
            self.cacheman = cacheout.Cache(maxsize=60)
        if "site_config" in self.config:
            with open(self.config["site_config"], "r") as f:
                self.site_config = f.read()
            buffer = self.site_config
            self.siteblacklist = []
            self.userblacklist = []
            self.redirectlist = []
            for line in buffer.split("\n"):
                if line[:15] == "siteblacklist: ":
                    self.siteblacklist.append(line[15:])
                elif line[:15] == "userblacklist: ":
                    self.userblacklist.append(line[15:])
                elif line[:15] == "redirectlist : ":
                    temp = line[15:]
                    pos = temp.find("->")
                    if pos == -1:
                        continue
                    else:
                        self.redirectlist.append((temp[:pos], temp[pos + 2:]))
                else:
                    continue
        # self.cacheDB = {}

    def run(self):
        while True:
            (clientSocket, client_address) = self.serverSocket.accept()
            logging.info("accept connect from " + client_address.__str__())
            # self.proxy_thread(clientSocket,client_address)
            # d = threading.Thread(target=self.proxy_thread,args=(clientSocket,client_address),daemon=True)
            # d.start()
            self.pool.submit(self.proxy_thread, clientSocket, client_address)

    def proxy_thread(self, clientsocket: socket.socket, clientaddress):
        # parse the http to get host and port
        request = clientsocket.recv(1000).decode()

        # filter the request ,if there some blacklist or redirectlist.
        filtered, newrequest = self._process(request)  # filter the request.
        if filtered:
            logging.info("filter this request : " + str(clientaddress))
            clientsocket.close()
            return
        else:
            request = newrequest

        ## cache for request.if hit, it is no need for a new object transport.
        hit, data = self.cachehit(request)
        if hit:
            logging.info("hitting this cache : " + str(clientaddress))
            clientsocket.send(data)
            clientsocket.close()
            return

        # basic forward for request.
        host, port = self._getAdress(request)
        try:
            receive = self._sendto_remote_server(request, host, port)
        except TimeoutError:
            logging.info("fail timeout to connect " + (host, port).__str__())
            return
        self.cacheadd(request, receive)  # add key value to cacheman, add(request,receive)
        clientsocket.send(receive)
        clientsocket.close()

    def _process(self, request: str) -> (bool, str):
        '''
        if filter return true ,otherwise return false
        :param request: client request
        :return: return a bool,and a new request
        '''
        if self.site_config == "":
            return (False, request)
        host = self._getHost(request)
        user = self._getUser(request)
        for site in self.siteblacklist:
            if host.find(site) != -1:
                logging.info("filter hitting " + site)
                return (True, request)
        for u in self.userblacklist:
            if user.find(u) != -1:
                logging.info("filter hitting " + u)
                return (True, request)

        for a, b in self.redirectlist:
            if request.find(a) != -1:
                r = request.replace(a, b)
                logging.info("redirect from " + a + " to " + b)
                return (False, r)
            else:
                continue

        return (False, request)

    def cachehit(self, request) -> (bool, bytes):
        '''
        cache for proxyserver
        :param request: client request
        :return: return true for hitting the cache ,otherwise return false
        '''
        if not self.config["cache"]:
            return (False, "")

        if self._getModifiedline(request) != "":
            return (False, "")
        ## parse the http to get resource location
        first_line = request.split("\r\n")[0]
        # if self.cacheDB.has_key(resource_location):
        #    logging.info("hit a cache for "+resource_location)
        host, port = self._getAdress(request)
        resource_location = "http://" + host + ":" + str(port) + first_line.split(" ")[1]
        if not self.cacheman.has(resource_location):
            return (False, "")
        ## cacheman is (resource_location:(timestamp,bytesContent))
        logging.info("hit in the cahe of " + resource_location)
        timestamp, bytesContent = self.cacheman.get(resource_location)
        newrequest = request[:-2] + "If-Modified-Since: " + timestamp + "\r\n" + request[-2:]
        receive = self._sendto_remote_server(newrequest, host, port)
        #       add if-modified line to request and sendtoremoteServer.
        #       if 304 , return bytesContent
        #       else ,return false.
        if str(receive).split("\r\n")[0].split(" ")[1] == "304":
            logging.info(resource_location + " isn't modified since " + timestamp)
            return (True, bytesContent)
        elif str(receive).split("\r\n")[0].split(" ")[1] == "200":
            logging.info(resource_location + " has modified since " + timestamp)
            return (True, receive)
        else:
            return (False, "")

    def cacheadd(self, request: str, achieve: bytes):
        str_achieve = achieve.decode('utf-8', 'replace')
        if not self.config["cache"]:
            return
        if not str_achieve.split("\r\n")[0].split(" ")[1] == "200":
            return

        dateStamp = self._getDate(str_achieve)
        if dateStamp == "":
            return

        first_line = request.split("\r\n")[0]
        host, port = self._getAdress(request)
        resource_location = "http://" + host + ":" + str(port) + first_line.split(" ")[1]

        self.cacheman.add(key=resource_location, value=(dateStamp, achieve))

    def _getHost(self, request):
        '''
        this function return contains port may be
        :param request: client request
        :return: return host (may with port),if none return ""
        '''
        result = ""
        for line in request.split("\r\n"):
            if line[:6] == "Host: ":
                result = line[6:]
                break
        return result

    def _getUser(self, request):
        result = ""
        for line in request.split("\r\n"):
            if line[:12] == "User-Agent: ":
                result = line[12:]
                break
        return result

    def _getAdress(self, request) -> (str, int):
        '''
        get address
        :param request: client request
        :return: str->ip or host address ,int->port
        '''
        temp = self._getHost(request)
        if temp == "":
            temp = request.split("\r\n")[0].split(" ")[1]
        pos = temp.find(":")
        if pos == -1:
            port = 80
            host = temp
        else:
            host = temp[:pos]
            port = int(temp[pos + 1:])
        return (host, port)

    def _getModifiedline(self, request: str) -> str:
        time = ""
        for line in request.split("\r\n"):
            if line[:19] == "If-Modified-Since: ":
                time = line[19:]
                break
        return time

    def _getDate(self, receive: str) -> str:
        date = ""
        for line in receive.split("\r\n"):
            if line[:6] == "Date: ":
                date = line[6:]
                break
        return date

    def _sendto_remote_server(self, request: str, host, port) -> bytes:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logging.info("try to connect dst address " + (host, port).__str__())
        s.connect((host, port))
        s.send(request.encode())
        receive = b''
        while True:
            data = s.recv(1000)
            if len(data) > 0:
                receive += data
            else:
                break
        s.close()
        return receive
