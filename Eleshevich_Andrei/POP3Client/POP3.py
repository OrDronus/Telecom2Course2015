__author__ = 'Andrew'
import socket
import email
import ssl
from datetime import datetime


def decode_payload(message):
    if message.is_multipart():
        res = ""
        for part in message.get_payload():
            res += decode_payload(part)
        return res
    elif message.get_content_type() == "text/plain":
        if message.get("Content-Transfer-Encoding") != "8bit":
            return message.get_payload(decode=True).decode(message.get_content_charset() or "utf-8", "replace")
        else:
            return message.get_payload()
    else:
        return ""


def decode_head(msg):
    res = ""
    for part in email.header.decode_header(msg):
        def_charset = "utf-8"
        if type(part[0]) is bytes:
            res += part[0].decode(part[1] or def_charset)
        else:
            res += part[0]
    return res


class POP3(object):
    def __init__(self, logname):
        self.log = open(logname, "a")
        self.sock = None
        self.buff = None

    def __del__(self):
        self.log.close()

    def connect(self, hostname, port, use_ssl=False):
        if self.sock is not None:
            self.sock.close()
            self.buff.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if not self.sock:
            raise RuntimeError("Can't create socket")
        if use_ssl:
            self.sock = ssl.wrap_socket(self.sock)
        self.buff = self.sock.makefile("r")
        self.sock.connect((hostname, port))
        ans = self.buff.readline()
        return ans[:3] == "+OK"

    def sendMsg(self, message):
        if self.sock.send(message.encode()) == 0:
            self.sock.close()
            raise RuntimeError("Connection lost")
        self.log.write("[%s]Client: %s" % (datetime.now().strftime("%d.%m.%y %H:%M:%S:%f"), message))
        ans = self.buff.readline()
        if ans == "":
            self.sock.close()
            raise RuntimeError("Connection lost")
        self.log.write("[%s]Server: %s" % (datetime.now().strftime("%d.%m.%y %H:%M:%S:%f"), ans))
        return ans

    def noop(self):
        ans = self.sendMsg("NOOP\n")
        if ans[:3] == "+OK":
            return True
        else:
            return False

    def login(self, login, password):
        self.sendMsg("USER %s\n" % login)
        ans = self.sendMsg("PASS %s\n" % password)
        if ans[:3] != "+OK":
            return False
        return True

    def stat(self):
        ans = self.sendMsg("STAT\n")
        ok, num, size = ans.split()
        return int(num), int(size)

    def list(self):
        ans = self.sendMsg("LIST\n")
        if ans[:3] != "+OK":
            print(ans[4:])
            return False
        res = []
        while True:
            line = self.buff.readline()
            if line == ".\n":
                break
            res.append(int(line.split()[1]))
        return res

    def delete(self, num):
        ans = self.sendMsg("DELE %d\n" % num)
        return ans[:3] == "+OK"

    def rset(self):
        ans = self.sendMsg("RSET\n")
        return ans[:3] == "+OK"

    def uidl(self, num=0):
        res = []
        if num > 0:
            sans = self.sendMsg("UIDL %d\n" % num).split()
            if sans[0] != "+OK":
                return False
            res.append((int(sans[1]), sans[2]))
        else:
            self.sendMsg("UIDL\n")
            while True:
                sline = self.buff.readline().split()
                if sline[0] == ".":
                    break
                res.append((int(sline[0]), sline[1]))
        return res

    # Более подробный список
    def alist(self):
        res = []
        list = self.list()
        for i, size in enumerate(list):
            head = self.top(i+1)
            message = {"Size": size, "Subject": decode_head(head.get("Subject") or ""),
                       "From": decode_head(head.get("From")), "Date": head.get("Date")}
            res.append(message)
        return res

    def top(self, num, lines=0):
        ans = self.sendMsg("TOP %d %d\n" % (num, lines))
        if ans[:3] != "+OK":
            return False
        text = ""
        while True:
            line = self.buff.readline()
            if line == ".\n":
                break
            text += line
        return email.message_from_string(text)

    def retr(self, num):
        ans = self.sendMsg("RETR %s\n" % num)
        if ans[:3] != "+OK":
            return False
        text = ""
        while True:
            line = self.buff.readline()
            if line == ".\n":
                break
            text += line
        return email.message_from_string(text)

    def quit(self):
        ans = self.sendMsg("QUIT\n")
        self.sock.close()
        self.buff.close()
        return ans[4:]