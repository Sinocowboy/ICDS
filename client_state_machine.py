from chat_utils import *
import json

class ClientSM:
    def __init__(self, s):
        self.state = S_OFFLINE
        self.peer = ''
        self.me = ''
        self.out_msg = ''
        self.s = s

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def set_myname(self, name):
        self.me = name

    def get_myname(self):
        return self.me

    def connect_to(self, peer):
        msg = json.dumps({"action": "connect", "target": peer})
        mysend(self.s, msg)
        raw_response = myrecv(self.s)
        self.out_msg = ''

        if not raw_response:
            self.out_msg += "Connection failed: No response from server.\n"
            return False

        try:
            response = json.loads(raw_response)
            status = response.get("status", "unknown")

            if status == "success":
                self.peer = peer
                return True
            elif status == "busy":
                self.out_msg += f"User '{peer}' is busy. Please try again later.\n"
            elif status == "self":
                self.out_msg += "Cannot talk to yourself (sick).\n"
            else:
                self.out_msg += f"User '{peer}' not online or connection failed ({status}).\n"
        except Exception as err:
            self.out_msg += f"Connection failed: Invalid response from server ({err}). Response: '{raw_response}'\n"

        return False

    def disconnect(self):
        peer_name = self.peer
        self.peer = ''
        msg = json.dumps({"action": "disconnect"})
        mysend(self.s, msg)
        if peer_name:
             self.out_msg += f'You initiated disconnect from {peer_name}\n'

    def proc(self, my_msg, peer_msg=""):
        self.out_msg = ''

        if self.state == S_LOGGEDIN:
            if len(my_msg) > 0:
                if my_msg == 'q':
                    self.out_msg += 'See you next time!\n'
                    self.state = S_OFFLINE
                elif my_msg == 'time':
                    mysend(self.s, json.dumps({"action": "time"}))
                    try:
                        response = json.loads(myrecv(self.s))
                        time_in = response.get("results", "Error getting time")
                        self.out_msg += "Time is: " + time_in + "\n"
                    except Exception as err:
                        self.out_msg += f"Error getting time: {err}\n"
                elif my_msg == 'who':
                    mysend(self.s, json.dumps({"action": "list"}))
                    try:
                        response = json.loads(myrecv(self.s))
                        logged_in = response.get("results", "Error getting list")
                        self.out_msg += 'Users online:\n----------\n' + logged_in + "\n----------\n"
                    except Exception as err:
                         self.out_msg += f"Error getting user list: {err}\n"
                elif my_msg.startswith('c '):
                    peer = my_msg[2:].strip()
                    if len(peer) > 0:
                        if self.connect_to(peer):
                            self.state = S_CHATTING
                            self.out_msg += f'Connection to {peer} established.\n'
                            self.out_msg += 'Chat away! (type "bye" to disconnect)\n'
                            self.out_msg += '-----------------------------------\n'
                    else:
                        self.out_msg += "Please specify a user to connect to (e.g., c alice).\n"

                elif my_msg.startswith('? '):
                    term = my_msg[2:].strip()
                    if len(term) > 0:
                        mysend(self.s, json.dumps({"action": "search", "target": term}))
                        try:
                            response = json.loads(myrecv(self.s))
                            search_rslt = response.get("results", [])
                            if isinstance(search_rslt, list) and len(search_rslt) > 0:
                                self.out_msg += f"Search results for '{term}':\n" + "\n".join(search_rslt) + '\n\n'
                            else:
                                self.out_msg += f"'{term}' not found.\n\n"
                        except Exception as err:
                            self.out_msg += f"Error during search: {err}\n\n"
                    else:
                        self.out_msg += "Please specify a search term (e.g., ? hello).\n\n"

                elif my_msg.startswith('p ') and my_msg[2:].strip().isdigit():
                    poem_idx = my_msg[2:].strip()
                    mysend(self.s, json.dumps({"action": "poem", "target": poem_idx}))
                    try:
                        response = json.loads(myrecv(self.s))
                        poem = response.get("results", "")
                        if isinstance(poem, str) and len(poem) > 0:
                            self.out_msg += f"--- Sonnet {poem_idx} ---\n{poem}\n-------------------\n\n"
                        else:
                            self.out_msg += f"Sonnet {poem_idx} not found.\n\n"
                    except Exception as err:
                         self.out_msg += f"Error getting poem: {err}\n\n"
                else:
                    self.out_msg += menu

            if len(peer_msg) > 0:
                try:
                    peer_msg_dict = json.loads(peer_msg)
                    action = peer_msg_dict.get("action", "").lower()

                    if action == "connect":
                        peer_name = peer_msg_dict.get("from", "Unknown")
                        self.peer = peer_name
                        connect_msg = peer_msg_dict.get("msg", f"Connected with {self.peer}")
                        self.out_msg += "-----------------------------------\n"
                        self.out_msg += f"Incoming connection from {peer_name}!\n"
                        self.out_msg += connect_msg + '\n'
                        self.state = S_CHATTING
                        self.out_msg += 'Chat away! (type "bye" to disconnect)\n'
                        self.out_msg += '------------------------------------\n'
                        return True

                except Exception as err:
                    self.out_msg += f"Received invalid message: {err}. Message: '{peer_msg}'\n"

        elif self.state == S_CHATTING:
            if len(my_msg) > 0:
                mysend(self.s, json.dumps({"action": "exchange", "from": self.me, "message": my_msg}))
                if my_msg == 'bye':
                    self.disconnect()
                    self.state = S_LOGGEDIN
                    self.out_msg += menu

            if len(peer_msg) > 0:
                try:
                    peer_msg_dict = json.loads(peer_msg)
                    action = peer_msg_dict.get("action", "").lower()

                    if action == "exchange":
                        sender = peer_msg_dict.get("from", "Unknown")
                        message = peer_msg_dict.get("message", "")
                        self.out_msg += f"{sender}: {message}\n"

                    elif action == "disconnect":
                        disconnect_msg = peer_msg_dict.get("msg", f"{self.peer} has disconnected.")
                        self.out_msg += "-----------------------------------\n"
                        self.out_msg += disconnect_msg + '\n'
                        self.state = S_LOGGEDIN
                        self.peer = ''
                        self.out_msg += menu

                    elif action == "connect":
                        joiner = peer_msg_dict.get("from", "Unknown")
                        self.out_msg += f"({joiner} joined the chat)\n"

                except Exception as err:
                     self.out_msg += f"Received invalid message while chatting: {err}. Message: '{peer_msg}'\n"

        else:
            self.out_msg += 'Error: Invalid state encountered.\n'
            try:
                self.out_msg += f"Current state value: {self.state}\n"
            except NameError:
                pass

        return self.out_msg
