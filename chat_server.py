import time
import socket
import select
import sys
import string
import indexer
import pickle as pkl
from chat_utils import *
import chat_group as grp
import json


class Server:
    def __init__(self):
        self.new_clients = []
        self.logged_name2sock = {}
        self.logged_sock2name = {}
        self.all_sockets = []
        self.group = grp.Group()
        self.server=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(SERVER)
        self.server.listen(5)
        self.all_sockets.append(self.server)
        self.indices={}
        self.sonnet = indexer.PIndex('AllSonnets.txt')


    def new_client(self, sock):
        print('new client...')
        sock.setblocking(0)
        self.new_clients.append(sock)
        self.all_sockets.append(sock)

    def login(self, sock):
        try:
            msg = json.loads(myrecv(sock))
            if len(msg) > 0:
                if msg["action"] == "login":
                    name = msg["name"]
                    if self.group.is_member(name) != True:
                        self.new_clients.remove(sock)
                        self.logged_name2sock[name] = sock
                        self.logged_sock2name[sock] = name
                        if name not in self.indices.keys():
                            try:
                                self.indices[name]=pkl.load(open(name+'.idx','rb'))
                            except IOError:
                                self.indices[name] = indexer.Index(name)
                        print(name + ' logged in')
                        self.group.join(name)
                        mysend(sock, json.dumps({"action":"login", "status":"success"}))
                    else:
                        mysend(sock, json.dumps({"action":"login", "status":"duplicate"}))
                        print(name + ' duplicate login attempt')
                else:
                    print ('wrong code received')
            else:
                self.logout(sock)
        except Exception as e:
             print(f"Login error: {e}")
             self.logout(sock)


    def logout(self, sock):
        if sock not in self.logged_sock2name:
            if sock in self.new_clients:
                self.new_clients.remove(sock)
            if sock in self.all_sockets:
                self.all_sockets.remove(sock)
            sock.close()
            return

        name = self.logged_sock2name[sock]
        print(name + ' logged out')
        if name in self.indices:
            pkl.dump(self.indices[name], open(name + '.idx','wb'))
            del self.indices[name]
        if name in self.logged_name2sock:
            del self.logged_name2sock[name]
        if sock in self.logged_sock2name:
            del self.logged_sock2name[sock]

        self.all_sockets.remove(sock)
        self.group.leave(name)
        sock.close()


    def handle_msg(self, from_sock):
        try:
            raw_msg = myrecv(from_sock)
            if len(raw_msg) > 0:
                msg = json.loads(raw_msg)
                action = msg.get("action", "")
                from_name = self.logged_sock2name.get(from_sock)
                if not from_name:
                     print("Error: Message from unknown logged-in socket")
                     self.logout(from_sock) 
                     return

                if action == "connect":
                    to_name = msg.get("target")
                    if to_name == from_name:
                        resp = {"action":"connect", "status":"self"}
                    elif self.group.is_member(to_name):
                        to_sock = self.logged_name2sock.get(to_name)
                        if self.group.connect(from_name, to_name):
                            the_guys = self.group.list_me(from_name)
                            resp = {"action":"connect", "status":"success"}
                        
                            peer_msg = {"action":"connect", "from":from_name, "msg": f"Connection request from {from_name}"}
                            mysend(to_sock, json.dumps(peer_msg))
                        else:
                            
                             resp = {"action":"connect", "status":"busy"}
                    else:
                        resp = {"action":"connect", "status":"no-user"}
                    mysend(from_sock, json.dumps(resp))

                elif action == "exchange":
                    the_guys = self.group.list_me(from_name)
                    message = msg.get("message", "")
                    said2 = text_proc(message, from_name) 
                    self.indices[from_name].add_msg_and_index(said2)

                    outgoing_msg = {"action":"exchange", "from":from_name, "message":message}

                    for g in the_guys:
                        if g != from_name:
                            to_sock = self.logged_name2sock.get(g)
                            if g in self.indices:
                                self.indices[g].add_msg_and_index(said2)
                            if to_sock:
                                mysend(to_sock, json.dumps(outgoing_msg))

                elif action == "list":
                    all_users = self.group.list_all()
                    resp = {"action":"list", "results": all_users}
                    mysend(from_sock, json.dumps(resp))

                elif action == "poem":
                    poem_idx_str = msg.get("target", "")
                    try:
                        poem_idx = int(poem_idx_str)
                        poem = self.sonnet.get_poem(poem_idx)
                        resp = {"action":"poem", "results":"\n".join(poem)}
                    except ValueError:
                        resp = {"action":"poem", "results": f"Error: Invalid index '{poem_idx_str}'"}
                    except IndexError:
                         resp = {"action":"poem", "results": f"Error: Sonnet {poem_idx_str} not found"}
                    mysend(from_sock, json.dumps(resp))

                elif action == "time":
                    ctime = time.strftime('%d.%m.%y, %H:%M', time.localtime())
                    resp = {"action":"time", "results":ctime}
                    mysend(from_sock, json.dumps(resp))

                elif action == "search":
                    term = msg.get("target", "")
                    search_rslt_idx = self.indices[from_name].search(term)
                    search_rslt = [str(i) for i in search_rslt_idx]
                    print(f'server side search for {from_name}: {term} -> {search_rslt}')
                    resp = {"action":"search", "results":search_rslt}
                    mysend(from_sock, json.dumps(resp))

                elif action == "disconnect":
                    the_guys = self.group.list_me(from_name)
                    if len(the_guys) > 1: 
                         peer_name = self.group.disconnect(from_name) 
                         if peer_name:
                             to_sock = self.logged_name2sock.get(peer_name)
                             if to_sock:
                                 peer_msg = {"action":"disconnect", "msg":f"{from_name} has disconnected."}
                                 mysend(to_sock, json.dumps(peer_msg))


                elif action == "logout": 
                    self.logout(from_sock)
                    return 

                else:
                    print(f"Unknown action received from {from_name}: {action}")
                    resp = {"action":"error", "message":f"Unknown action: {action}"}
                    mysend(from_sock, json.dumps(resp))

            else:
                self.logout(from_sock)
        except Exception as e:
             print(f"Error handling message: {e}")
             if from_sock in self.logged_sock2name:
                 self.logout(from_sock)
             else:
                  print("Error from unknown socket, attempting removal.")
                  if from_sock in self.new_clients: self.new_clients.remove(from_sock)
                  if from_sock in self.all_sockets: self.all_sockets.remove(from_sock)
                  from_sock.close()


    def run(self):
        print ('starting server...')
        while(1):
            read,write,error=select.select(self.all_sockets,[],[], 0.1)

            logged_sockets = list(self.logged_name2sock.values())
            for logc in logged_sockets:
                if logc in read:
                    self.handle_msg(logc)

            current_new_clients = self.new_clients[:]
            for newc in current_new_clients:
                 if newc in read:
                    self.login(newc)

            if self.server in read :
                sock, address = self.server.accept()
                self.new_client(sock)


def main():
    server = Server()
    server.run()

if __name__ == "__main__":
    main()
