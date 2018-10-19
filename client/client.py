import http.client
if __name__=="__main__" :
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    conn.connect()
    conn.request("GET","/index.html")
    response = conn.getresponse()
    data = response.read()
    print (data)
    conn.close()