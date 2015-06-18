__author__ = 'Andrew'
import socket
import threading
import os
import time
import shutil
import stat
from datetime import datetime


def loadConf(fname):
    fd = open(fname, "r")
    res = {"def_root": "", "port": "", "anon_root": ""}
    for line in fd:
        sline = line.split(maxsplit=1)
        if len(sline) < 2:
            continue
        if sline[0] in res:
            res[sline[0]] = sline[1].strip()
    return res


def loadUsers(fname):
    fd = open(fname, "r")
    res = {}
    for line in fd:
        sline = line.split(maxsplit=2)
        if len(sline) < 2 or sline[0] in res:
            continue
        if len(sline) < 3:
            rootFd = ""
        else:
            rootFd = sline[2].strip()
        res[sline[0]] = (sline[1], rootFd)
    return res


def list_dir(path):
    res = ""
    for name in os.listdir(path):
        try:
            stinfo = os.stat(os.path.join(path, name))
            if stat.S_ISDIR(stinfo.st_mode):
                size = 4096
            else:
                size = stinfo.st_size
            mtime = time.strftime("%b %m %H:%M", time.gmtime(stinfo.st_mtime))
            res += "%s 1 server server %d %s %s\n" % (stat.filemode(stinfo.st_mode), size, mtime, name)
        except OSError:
            pass
    return res[:len(res)-1]


class ConnectionClosedError(Exception):
    def __str__(self):
        return "Connection closed"


class NotEnoughParametersError(Exception):
    def __init__(self, commName):
        self.commName = commName

    def _str__(self):
        return "Command %s should have one parameter" % self.commName


class Logger(object):

    def __init__(self, fname, cons=False):
        self.lock = threading.Lock()
        self.fd = open(fname, "a")
        self.cons = cons

    def write(self, line):
        self.lock.acquire()
        if self.cons:
            print(line)
        self.fd.write("%s\n" % line)
        self.fd.flush()
        self.lock.release()

    def __del__(self):
        self.fd.close()


class MySocket(object):

    def __init__(self, sock):
        self.sock = sock
        self.buff = sock.makefile("rwb")

    def send(self, msg):
        if len(msg) == 0:
            return
        b = self.buff.write(msg)
        if b == 0:
            raise ConnectionClosedError()
        self.buff.flush()

    def recv(self, len=-1):
        if len == -1:
            data = self.buff.readline()
        else:
            data = self.buff.read(len)
        if not data:
            raise ConnectionClosedError()
        return data

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.buff.close()

    def getsockname(self):
        return self.sock.getsockname()

    def getpeername(self):
        return self.sock.getpeername()


class Client(threading.Thread):

    com = ""
    curDir = ""
    ttype = "A"
    dataConn = None
    clientName = ""
    block_size = 4096
    utf8 = False

    def __init__(self, sock, logger, defRoot, anonRoot=""):
        threading.Thread.__init__(self)
        self.sock = MySocket(sock)
        self.defRoot = defRoot  # Корневая папка по умолчанию
        self.anonRoot = anonRoot
        self.rootDir = anonRoot
        self.log = logger

    def getDirPath(self, name):
        if name[0] == "/":
            return name[1:]
        elif name == "..":
            return os.path.dirname(self.curDir)
        elif name == ".":
            return self.curDir
        else:
            return os.path.join(self.curDir, name)

    def recvComm(self):
        if self.utf8:
            self.com = self.sock.recv().decode("utf-8").strip()
        else:
            self.com = self.sock.recv().decode("ascii", "replace").strip()
        self.log.write("[%s] %s > %s" % (datetime.now().strftime("%d.%m.%y %H:%M:%S:%f"), self.clientName, self.com))
        return self.com.split()[0].upper()

    def sendResp(self, msg):
        if self.utf8:
            self.sock.send((msg + "\r\n").encode("utf-8"))
        else:
            self.sock.send((msg + "\r\n").encode("ascii", "replace"))
        self.log.write("[%s] %s < %s" % (datetime.now().strftime("%d.%m.%y %H:%M:%S:%f"), self.clientName, msg))

# Команды
    def noLoginResp(self):
        self.sendResp("530 Not logged in")

    def anonAccResp(self):
        self.sendResp("532 Action not available for anonymous users")

    def login(self):
        self.sendResp("331 Send password")
        user = self.com.split()[1]
        if user == "anonymous" and self.anonRoot:
            self.rootDir = self.anonRoot
            self.sendResp("230 Access granted")
            return 1
        try:
            passwd = users[user][0]
        except KeyError:
            passwd = ""
        if self.recvComm() != "PASS":
            self.sendResp("503 PASS command expected")
            return 0
        if not passwd or passwd != self.com.split()[1]:
            self.sendResp("530 Login incorrect")
            return 0
        else:
            dirName = users[user][1]
            if dirName and os.path.exists(dirName):
                self.rootDir = dirName
            else:
                self.rootDir = self.defRoot
            self.sendResp("230 Access granted")
            return 2

    def anonPass(self):
        self.sendResp("230 Access granted")

    def syst(self):
        self.sendResp("215 WINDOWS-NT Type: L8")

    def noop(self):
        self.sendResp("200 I'm here")

    def opts(self):
        scom = self.com.split()
        if scom[1].upper() != "UTF8":
            self.sendResp("501 Unknown command argument")
            return
        if len(scom) < 3:
            self.sendResp("501 Command option not specified")
            return
        if scom[2].upper() == "ON":
            self.utf8 = True
        else:
            self.utf8 = False
        self.sendResp("200 Options accepted")

    def feat(self):
        self.sendResp("211- Features supported:\n UTF8\n211 end")

    def pwd(self):
        if not self.curDir:
            self.sendResp("257 \"/\"")
        else:
            self.sendResp("257 \"/%s\"" % self.curDir)

    def cwd(self):
        newDir = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t\r"))
        fullPath = os.path.join(self.rootDir, newDir)
        if os.path.exists(fullPath) and os.path.isdir(fullPath):
            self.curDir = newDir
            self.sendResp("250 CWD successful")
        else:
            self.sendResp("431 No such directory")

    def cdup(self):
        if len(self.curDir) < 2:
            self.sendResp("431 No such directory")
        else:
            self.curDir = os.path.dirname(self.curDir)
            self.sendResp("200 CDUP successful")

    def pasv(self):
        self.dataConn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dataConn.bind((socket.gethostname(), 0))
        self.dataConn.listen(0)
        host, port = self.dataConn.getsockname()
        msg = "227 Entering Passive Mode (%s,%d,%d)." % (host.replace(".", ","), port >> 8, port & 0xff)
        self.sendResp(msg)

    def type(self):
        newType = self.com.split()[1]
        if newType == "A":
            self.sendResp("200 ASCII type set")
            self.ttype = type
        elif newType == "I":
            self.sendResp("200 Binary type set")
            self.ttype = newType
        else:
            self.sendResp("502 Type not implemented")

    def list(self):
        try:
            data = list_dir(os.path.join(self.rootDir, self.curDir))
            self.sendResp("150 Opening data connection")    # Может надо указать тип
            (newsock, address) = self.dataConn.accept()
            self.dataConn.close()
            self.dataConn = MySocket(newsock)
            if self.utf8:
                self.dataConn.send(data.encode("utf-8"))
            else:
                self.dataConn.send(data.encode("ascii", "replace"))
            self.dataConn.close()
            self.sendResp("226 Data transmission ok")
        except PermissionError:
            self.sendResp("550 No access permission")

    def retr(self):
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        fullPath = os.path.join(self.rootDir, path)
        try:
            fd = open(fullPath, "rb")
            self.sendResp("150 Opening data connection")    # Может надо указать тип
            (newsock, address) = self.dataConn.accept()
            self.dataConn.close()
            self.dataConn = MySocket(newsock)
            while True:
                data = fd.read(16384)
                if len(data) == 0:
                    break
                self.dataConn.send(data)
            self.dataConn.close()
            self.sendResp("226 Data transmission ok")
        except OSError:
            self.sendResp("550 Can't open the file")    # Может потом посмотреть код поточнее

    def stor(self):
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        fullPath = os.path.join(self.rootDir, path)
        try:
            fd = open(fullPath, "wb")
            self.sendResp("150 Opening data connection")    # Может надо указать тип
            (newsock, address) = self.dataConn.accept()
            self.dataConn.close()
            self.dataConn = MySocket(newsock)
            try:
                while True:
                    data = self.dataConn.recv(self.block_size)
                    fd.write(data)
            except RuntimeError:
                self.dataConn.close()
                self.sendResp("226 Data transmission ok")
        except OSError:
            self.sendResp("550 Can't create the file")    # Может потом посмотреть код поточнее

    def rename(self):
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        oldPath = os.path.join(self.rootDir, path)
        if not os.path.exists(oldPath):
            self.sendResp("550 File not found")
            return
        self.sendResp("350 Waiting for a new name")
        self.com = self.sock.recv()
        ans = self.com.split(maxsplit=1)
        if ans[0] != "RNTO":
            self.sendResp("503 RNTO was expected")
            return
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        newPath = os.path.join(self.rootDir, path)
        if os.path.exists(newPath):
            self.sendResp("553 Such path already exists")
            return
        os.rename(oldPath, newPath)
        self.sendResp("250 Rename successful")

    def dele(self):
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        fullPath = os.path.join(self.rootDir, path)
        if not os.path.exists(fullPath):
            self.sendResp("550 File not found")
            return
        try:
            os.remove(fullPath)
            self.sendResp("250 File successfully deleted")
        except OSError:
            self.sendResp("550 Can't access the file")

    def rmd(self):
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        fullPath = os.path.join(self.rootDir, path)
        if not os.path.exists(fullPath):
            self.sendResp("550 File not found")
            return
        try:
            shutil.rmtree(fullPath)
            self.sendResp("250 File successfully deleted")
        except OSError:
            self.sendResp("550 Can't access the file")

    def mkd(self):
        path = self.getDirPath(self.com.split(maxsplit=1)[1].strip("\"\n\t"))
        fullPath = os.path.join(self.rootDir, path)
        try:
            os.mkdir(fullPath)
            self.sendResp("250 Directory successfully created")
        except FileExistsError:
            self.sendResp("553 Directory with that name already exists")
        except OSError:
            self.sendResp("550 Can't create directory")

    anon_commands = {"PASS": anonPass, "SYST": syst, "FEAT": feat, "PWD": pwd, "CWD": cwd,
            "CDUP": cdup, "PASV": pasv, "TYPE": type, "LIST": list, "NOOP": noop,
            "RETR": retr, "STOR": anonAccResp, "RNFR": anonAccResp, "DELE": anonAccResp,
            "RMD": anonAccResp, "MKD": anonAccResp, "OPTS": opts}

    nl_commands = {"SYST": syst, "FEAT": feat, "PWD": noLoginResp,
               "CWD": noLoginResp, "CDUP": noLoginResp, "PASV": noLoginResp,
               "TYPE": noLoginResp, "LIST": noLoginResp, "NOOP": noop, "RETR": noLoginResp,
               "STOR": noLoginResp, "RNFR": noLoginResp, "DELE": noLoginResp,
               "RMD": noLoginResp, "MKD": noLoginResp, "OPTS": noLoginResp}

    user_commands = {"SYST": syst, "FEAT": feat, "PWD": pwd, "CWD": cwd,
            "CDUP": cdup, "PASV": pasv, "TYPE": type, "LIST": list, "NOOP": noop,
            "RETR": retr, "STOR": stor, "RNFR": rename, "DELE": dele, "RMD": rmd,
            "MKD": mkd, "OPTS": opts}

    acces_levels = [nl_commands, anon_commands, user_commands]

    def run(self):
        host, port = self.sock.getpeername()
        self.clientName = "%s:%d" % (host, port)
        logger.write("[%s] Client connected: %s" % (datetime.now().strftime("%d.%m.%y %H:%M:%S:%f"), self.clientName))
        self.sendResp("220 MyFTP ready")
        commands = self.nl_commands
        try:
            while True:
                command = self.recvComm()
                if command == "USER":
                    commands = self.acces_levels[self.login()]
                elif command == "QUIT":
                    self.sendResp("221 Bye bye")
                    break
                else:
                    try:
                        commands[command](self)
                    except KeyError:
                        self.sendResp("500 Command not recognized")
                    except NotEnoughParametersError as e:
                        self.sendResp("501 %s" % e)
        except ConnectionClosedError:
            pass
        self.log.write("[%s] Connection closed: %s" % (datetime.now().strftime("%d.%m.%y %H:%M:%S:%f"), self.clientName))
        self.sock.close()


users = loadUsers("users.txt")
cnf = loadConf("conf.txt")
logger = Logger("log.txt", True)

try:
    port = int(cnf["port"])
except ValueError:
    port = 21
servsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servsock.bind((socket.gethostname(), port))
servsock.listen(5)

defRoot = cnf["def_root"] or os.getcwd()

hostname, port = servsock.getsockname()
print("Server ready: %s:%d, Def root: %s%s" % (hostname, port, defRoot,
                                               ", Anon root: %s" % cnf["anon_root"] if cnf["anon_root"] else ""))

while True:
    (csock, address) = servsock.accept()
    client = Client(csock, logger, defRoot, cnf["anon_root"])
    client.start()