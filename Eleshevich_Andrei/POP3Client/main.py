__author__ = 'Andrew'
import socket
import ssl
import sys


class MySocket(object):
    blockSize = 4096

    def __init__(self, sock):
        self.sock = sock

    def send(self, msg):
        return self.sock.send(bytes(msg, 'ascii'))

    def recv(self):
        return self.sock.recv(self.blockSize).decode('ascii')


class POP3(object):
    blockSize = 4096
    def __init__(self, logname):
        self.log = open(logname, "a")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock = ssl.wrap_socket(self.sock)
        self.buff = self.sock.makefile()

    def connect(self, hostname, port):
        self.sock.connect((hostname, port))
        ans = self.sock.recv(self.blockSize).decode()
        #self.log.write("Server:", ans)
        #debug
        print("Connect:", ans)
        return ans[:3] == "+OK"

    def _sendMsg(self, message):
        self.sock.send(message.encode())
        self.log.write("Client: %s" % message)
        print("Client: %s" % message)             #debug
        ans = self.buff.readline()
        self.log.write("Server: %s" % ans)
        print("Server: %s" % ans)                 #debug
        return ans

    def login(self, login, password):
        ans = self._sendMsg("USER %s\n" % login)
        if ans[:3] != "+OK":
            return False
        ans = self._sendMsg("PASS %s\n" % password)
        if ans[:3] != "+OK":
            return False
        return True

    def stat(self):
        ans = self._sendMsg("STAT\n")
        ok, num, size = ans.split()
        return int(num), int(size)

    def list(self):
        ans = self._sendMsg("LIST\n")
        if ans[:3] != "+OK":
            return False
        res = []
        while True:
            line = self.buff.readline()
            if line == ".\n":
                break
            res.append(int(line.split()[1]))
        return res

    def top(self, num):
        ans = self._sendMsg("LIST\n")


    def quit(self):
        ans = self._sendMsg("QUIT\n")
        self.sock.close()
        self.buff.close()
        return ans

#Это должно задаваться в программе, но пока что будет так
host = "pop.rambler.ru"     #ip адрес/доменное имя сервера
port = 995                  #порт на сервере
user = ""           #логин пользователя
password = ""       #пароль пользователя

logname = "log.txt"         #имя файла для ведения лога сообщений

client = POP3("log.txt")
if not client.connect(host, port):
    print("Could not connect")
    sys.exit(-1)
if not client.login(user, password):
    print("Login or password is incorrect")
num, size = client.stat()
print("%s messages, %s bytes total" % (num, size))
lst = client.list()
print("List of letters:")
for i, x in enumerate(lst):
    print("%s) size:%s" % (i+1, x))
ans = client.quit()
print(ans)

"""sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock = ssl.wrap_socket(sock)
sock.connect((host, port))
fsock = sock.makefile('rw')
ans = fsock.readline()
print("Server: [%s]" % ans)
while 1:
    msg = input("Client: ")
    fsock.write(msg + "\n")
    ans = fsock.readline()
    print("Server: [%s]" % ans)
    if msg == "QUIT":
        break
sock.close()"""