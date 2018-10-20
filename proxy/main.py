from proxy import proxyServer

# it can be tested ues http://today.hit.edu.cn
if __name__=="__main__":
    config = {"host_name":"127.0.0.1","bind_port":10000,"max_request_len":1000,"timeout":100,"max_connect":10,"max_thread":10,"cache":True,
              "site_config":"site.config"}
    server = proxyServer.proxyServer(config)
    server.run()
