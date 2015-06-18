__author__ = 'Andrew'
import POP3
import sys
import threading


def load_conf(fname):
    res = {"hostname": "", "port": "0", "ssl": ""}
    try:
        c_file = open(fname)
        for line in c_file:
            sline = line.split()
            if len(sline) == 0:
                break
            res[sline[0]] = sline[1]
        res["port"] = int(res["port"])
        res["ssl"] = res["ssl"] == "True"
    except OSError:
        raise RuntimeError("Config file not found")
    except (IndexError, ValueError):
        raise RuntimeError("Config file is invalid")
    return res


class KeepAlive(threading.Thread):

    def __init__(self, lock, connection):
        threading.Thread.__init__(self)
        self.lock = lock
        self.conn = connection
        self.flag = threading.Event()

    def stop(self):
        self.flag.set()

    def run(self):
        while True:
            if self.flag.wait(10):
                break
            self.lock.acquire()
            self.conn.noop()
            self.lock.release()


class Console(object):

    def __init__(self, client):
        self.client = client
        self.command = []

    def com_list(self):
        lst = self.client.alist()
        for i, msg in enumerate(lst):
            print(str(i+1) + ")Subject: %(Subject)s Size: %(Size)s\nFrom: %(From)s Date: %(Date)s\n" % msg)

    def com_stat(self):
        num, size = self.client.stat()
        print("%s messages, %s bytes total" % (num, size))

    def com_delete(self):
        if self.client.delete(int(self.command[1])):
            print("Message deleted")
        else:
            print("No such message")

    def com_rset(self):
        self.client.rset()
        print("Message deletion aborted")

    def com_uidl(self):
        if len(self.command) == 1:
            lst = self.client.uidl()
        else:
            lst = self.client.uidl(int(self.command[1]))
        for i in lst:
            print("%d) %s" % (i[0], i[1]))

    def com_retr(self):
        message = self.client.retr(int(self.command[1]))
        if not message:
            print("No such message")
        else:
            print("Subject: %s\nFrom: %s" %
                  (POP3.decode_head(message.get("Subject")), POP3.decode_head(message.get("From"))))
            print("Date: %s\n" % message.get("Date"))
            print(POP3.decode_payload(message))

    def com_help(self):
        print("list: list of all messages\nstst: number of messages and their overall size\n\
delete msg: delete chosen message\nrollback: cancel deletion of all messages in this session\
uidl [msg]: get unique-id listing of selected message, or for all messages as a list\
retr msg: retrive chosen message\nquit: break connection and exit the programm\n\
(all messages, marked for deletion will be deleted permanently)\nhelp: show this help message")

    commands = {"list": com_list, "stat": com_stat, "delete": com_delete, "rollback": com_rset,
                "uidl": com_uidl, "retr": com_retr, "help": com_help}

    def exec_command(self, command):
        self.command = command.split()
        try:
            self.commands[self.command[0]](self)
        except KeyError:
            print("No such command")
        except IndexError:
            print("Not enough command parameters")
        except ValueError:
            print("Incorrect parameter type (need a number)")

    def login(self):
        while True:
            user = input("Enter login: ")
            password = input("Enter password: ")
            try:
                self.client.noop()
            except RuntimeError:
                if not self.client.connect(host, port, use_ssl):
                    print("Could not connect to POP3 server (hostname: %s port: %s)" % (host, port))
                    sys.exit(-1)
            if not self.client.login(user, password):
                print("Incorrect username/password")
            else:
                break
        print("Login successful")

port = 110          # порт на сервере
use_ssl = False     # использование ssl

conf = load_conf("config.txt")
if not conf["hostname"]:
    print("Hostname is not specified in config file")
    sys.exit(-1)
host = conf["hostname"]
if conf["port"]:
    port = conf["port"]
if conf["ssl"]:
    use_ssl = conf["ssl"]

pop3 = POP3.POP3("log.txt")
if not pop3.connect(host, port, use_ssl):
    print("Could not connect to POP3 server (hostname: %s port: %s)" % (host, port))
    sys.exit(-1)
console = Console(pop3)
console.login()
lock = threading.Lock()
keepAlive = KeepAlive(lock, pop3)
keepAlive.start()
while True:
    line = input(">")
    if line == "quit":
        break
    else:
        lock.acquire()
        console.exec_command(line)
        lock.release()
keepAlive.stop()
keepAlive.join()
ans = pop3.quit()
print(ans)