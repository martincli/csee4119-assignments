import socket, select, sys, time, threading

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Usage: python server.py <PORT>"

    else:
        host = socket.gethostbyname(socket.gethostname())  # host IP
        port = int(sys.argv[1])                            # port number
        MAX_USERS = 10  # maximum number of clients

        passwords = {}  # dictionary of usernames -> passwords
        connected = []  # list of connected sockets (not necessarily logged in yet)
        logged_in = {}  # dictionary of logged in sockets -> usernames
        last_logged_in = {}  # dictionary of usernames -> last logged in time

        # for login logic
        user_prompted = []  # list of sockets that have been prompted for username
        pass_prompted = {}  # dictionary of sockets -> usernames that have been prompted for password

        # for failed login blocking
        BLOCK_TIME = 60   # time in seconds to block
        failures = {}     # dictionary of sockets -> number of failures
        blocked_ips = {}  # dictionary of IP addresses -> time of block

        # for automatic logout
        TIME_OUT = 300     # time in seconds until automatic logout
        last_command = {}  # dictionary of sockets -> time of last command

        # for private messaging
        private_msgs = {}  # dictionary of usernames -> list of messages
        block_list = {}    # dictionary of usernames -> list of blocked usernames
        friends_list = {}  # dictionary of usernames -> list of friend usernames

        # for wholasthr
        LAST_HOUR = 3600  # time in seconds to check for recently connected users

        #====================================
        # Load usernames/passwords from file
        #====================================
        file = open('user_pass.txt')
        for line in file:
            words = line.split()
            passwords[words[0]] = words[1]

        #=======================
        # Start server + listen
        #=======================
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((host, port))
        print 'Chat server started.'
        print 'HOST: ' + host
        print 'PORT: ' + str(port)
        connected.append(server)
        server.listen(MAX_USERS)

        #=====================================
        # Periodic status check
        # - automatic logout for inactivity
        # - automatic logout for exited users
        # - update last logged in time
        #=====================================
        def status_check():
            for socket in logged_in.copy().keys():

                # logout inactive users
                if (time.time() - last_command[socket]) >= TIME_OUT:
                    try:
                        socket.send('time_logout')
                        del logged_in[socket]
                        connected.remove(socket)
                        socket.close()
                    except:
                        pass

                # logout non-existent users (e.g. exited with ctrl+C)
                try:
                    socket.send('status_check')
                except:
                    try:
                        del logged_in[socket]
                        connected.remove(socket)
                        socket.close()
                    except:
                        pass

                # update last logged in time
                try:
                    last_logged_in[logged_in[socket]] = time.time()
                except:
                    pass

            threading.Timer(3, status_check).start()
        status_check()

        #===========================
        # Process data from sockets
        #===========================
        while True:
            read_sockets,write_sockets,error_sockets = select.select(connected,[],[])
            for socket in read_sockets:

                #================
                # New connection
                #================
                if socket == server:
                    connection,address = server.accept()

                    # IP is currently blocked
                    if address[0] in blocked_ips and (time.time() - blocked_ips[address[0]]) <= BLOCK_TIME:
                        connection.send('ERROR: Your IP is currently blocked for too many failed login attempts.\nTime remaining: ' + str(round(BLOCK_TIME - (time.time() - blocked_ips[address[0]]), 1)) + ' seconds.\n\n')
                        connection.close()

                    # prompt user for username
                    else:
                        connection.send('Username: ')
                        connected.append(connection)
                        user_prompted.append(connection)

                else:
                    #================
                    # Authentication
                    #================
                    try:
                        # receive response for username
                        if socket in user_prompted:
                            user_response = socket.recv(4096).rstrip()

                            # prompt user for password
                            if user_response in passwords:
                                socket.send('Password: ')
                                user_prompted.remove(socket)
                                pass_prompted[socket] = user_response
                                failures[socket] = 0

                            # username does not exist
                            else:
                                socket.send('That username does not exist.\n\nUsername: ')
                        
                        # receive response for password
                        elif socket in pass_prompted:
                            pass_response = socket.recv(4096).rstrip()
                            user = pass_prompted[socket]

                            if passwords[user] == pass_response:

                                # username already logged in
                                if user in logged_in.values():
                                    socket.send('ERROR: That user is already logged in.\n\n')
                                    del failures[socket]
                                    del pass_prompted[socket]

                                # successful login
                                else:
                                    welcome_msg = 'Successfully logged in.\n'

                                    # show offline messages and then clear them
                                    if user in private_msgs:
                                        welcome_msg += '\nOffline messages:\n'
                                        for message in private_msgs[user]:
                                            welcome_msg += message + '\n'
                                        del private_msgs[user]

                                    socket.send(welcome_msg)
                                    del failures[socket]
                                    del pass_prompted[socket]
                                    logged_in[socket] = user
                                    last_command[socket] = time.time()

                            else:
                                # failure limit reached, IP blocked
                                if failures[socket] >= 2:
                                    socket.send('ERROR: Password retry limit reached. Try again in ' + str(BLOCK_TIME) + ' seconds.\n\n')
                                    blocked_ips[socket.getsockname()[0]] = time.time()
                                    connected.remove(socket)
                                    socket.close()

                                # increment failure count and try again
                                else:
                                    failures[socket] += 1
                                    socket.send('Incorrect username/password combination.\n\nPassword: ')

                        #==========================
                        # Receive data from client
                        #==========================
                        else:
                            last_command[socket] = time.time()
                            data = socket.recv(4096).rstrip()

                            data_split = data.split(' ',1)
                            command = data_split[0]
                            if len(data_split) > 1:
                                arguments = data_split[1]
                            else:
                                arguments = ''

                            #==================
                            # Command: whoelse
                            #==================
                            if command == 'whoelse':
                                if arguments:
                                    socket.send('\r[Server] Usage: whoelse\n')
                                else:
                                    userlist = '\r[Server] Currently logged in:\n'
                                    for username in logged_in.values():
                                        if username != logged_in[socket]:
                                            userlist += username + '\n'
                                    socket.send(userlist)

                            #====================
                            # Command: wholasthr
                            #====================
                            if command == 'wholasthr':
                                if arguments:
                                    socket.send('\r[Server] Usage: wholasthr\n')
                                else:
                                    userlist = '\r[Server] Connected in past hour:\n'
                                    for username in last_logged_in:
                                        if (time.time() - last_logged_in[username] < LAST_HOUR) and username != logged_in[socket]:
                                            userlist += username + '\n'
                                    socket.send(userlist)

                            #=================
                            # Command: logout
                            #=================
                            if command == 'logout':
                                if arguments:
                                    socket.send('\r[Server] Usage: logout\n')
                                else:
                                    socket.send('logout')
                                    del logged_in[socket]
                                    connected.remove(socket)
                                    socket.close()

                            #====================
                            # Command: broadcast
                            #====================
                            elif command == 'broadcast':
                                if arguments:
                                    for user in logged_in.keys():
                                        try:
                                            user.send('\r[Public] ' + logged_in[socket] + ': ' + arguments + '\n')
                                        except:
                                            user.close()
                                            connected.remove(socket)
                                            del logged_in[user]
                                else:
                                    socket.send('\r[Server] Usage: broadcast <MESSAGE>\n')

                            #==================
                            # Command: message
                            #==================
                            elif command == 'message':
                                if arguments:
                                    arguments_split = arguments.split(' ',1)
                                    if len(arguments_split) < 2:
                                        socket.send('\r[Server] Usage: message <USER> <MESSAGE>\n')
                                    else:
                                        receiver = arguments_split[0]
                                        msg = arguments_split[1]
                                        if receiver == logged_in[socket]:
                                            socket.send('\r[Server] ERROR: You cannot message yourself.\n')
                                        else:

                                            # blocked by receiving user
                                            if receiver in block_list and logged_in[socket] in block_list[receiver]:
                                                socket.send('\r[Server] ERROR: You have been blocked by this user.\n')
                                            
                                            else:
                                                if receiver in passwords:

                                                    # online message
                                                    if receiver in logged_in.values():
                                                        for user_socket, username in logged_in.items():
                                                            if username == receiver:
                                                                user = user_socket 
                                                        try:
                                                            socket.send('\r[Server] Message sent.\n')
                                                            user.send('\r[Private] ' + logged_in[socket] + ': ' + msg + '\n')
                                                        except:
                                                            user.close()
                                                            connected.remove(socket)
                                                            del logged_in[user]
                                                    
                                                    # offline message
                                                    else:
                                                        socket.send('\r[Server] Message sent.\n')
                                                        if receiver in private_msgs:
                                                            private_msgs[receiver].append('[Private] ' + logged_in[socket] + ': ' + msg)
                                                        else:
                                                            private_msgs[receiver] = ['[Private] ' + logged_in[socket] + ': ' + msg]
                                                else:
                                                    socket.send('\r[Server] ERROR: That user does not exist.\n')
                                else:
                                    socket.send('\r[Server] Usage: message <USER> <MESSAGE>\n')

                            #================
                            # Command: block
                            #================
                            elif command == 'block':
                                if arguments:
                                    if arguments in passwords:
                                        username = logged_in[socket]
                                        if arguments == username:
                                            socket.send('\r[Server] ERROR: You cannot block yourself.\n')
                                        else:
                                            if username in block_list:
                                                if arguments in block_list[username]:
                                                    socket.send('\r[Server] ERROR: That user is already blocked.\n')
                                                else:
                                                    block_list[username].append(arguments)
                                                    socket.send('\r[Server] User blocked.\n')
                                            else:
                                                block_list[username] = [arguments]
                                                socket.send('\r[Server] User blocked.\n')
                                    else:
                                        socket.send('\r[Server] ERROR: That user does not exist.\n')
                                else:
                                    socket.send('\r[Server] Usage: block <USER>\n')

                            #==================
                            # Command: unblock
                            #==================
                            elif command == 'unblock':
                                if arguments:
                                    username = logged_in[socket]
                                    if username in block_list:
                                        if arguments in block_list[username]:
                                            block_list[username].remove(arguments)
                                            socket.send('\r[Server] User unblocked.\n')
                                        else:
                                            socket.send('\r[Server] ERROR: That user is not blocked.\n')
                                    else:
                                        socket.send('\r[Server] ERROR: That user is not blocked.\n')
                                else:
                                    socket.send('\r[Server] Usage: unblock <USER>\n')

                            #====================
                            # Command: addfriend
                            #====================
                            elif command == 'addfriend':
                                if arguments:
                                    if arguments in passwords:
                                        username = logged_in[socket]
                                        if arguments == username:
                                            socket.send('\r[Server] ERROR: You cannot friend yourself.\n')
                                        else:
                                            if username in friends_list:
                                                if arguments in friends_list[username]:
                                                    socket.send('\r[Server] ERROR: That user is already a friend.\n')
                                                else:
                                                    friends_list[username].append(arguments)
                                                    socket.send('\r[Server] User added as friend.\n')
                                            else:
                                                friends_list[username] = [arguments]
                                                socket.send('\r[Server] User added as friend.\n')
                                    else:
                                        socket.send('\r[Server] ERROR: That user does not exist.\n')
                                else:
                                    socket.send('\r[Server] Usage: addfriend <USER>\n')

                            #=======================
                            # Command: removefriend
                            #=======================
                            elif command == 'removefriend':
                                if arguments:
                                    username = logged_in[socket]
                                    if username in friends_list:
                                        if arguments in friends_list[username]:
                                            friends_list[username].remove(arguments)
                                            socket.send('\r[Server] Friend removed.\n')
                                        else:
                                            socket.send('\r[Server] ERROR: That user is not a friend.\n')
                                    else:
                                        socket.send('\r[Server] ERROR: That user is not a friend.\n')
                                else:
                                    socket.send('\r[Server] Usage: removefriend <USER>\n')

                            #======================
                            # Command: viewfriends
                            #======================
                            if command == 'viewfriends':
                                if arguments:
                                    socket.send('\r[Server] Usage: viewfriends\n')
                                else:
                                    friends = '\r[Server] My friends:\n'
                                    username = logged_in[socket]
                                    if username in friends_list:
                                        for friend in friends_list[username]:
                                            friends += friend + '\n'
                                    socket.send(friends)

                            #=========================
                            # Command: messagefriends
                            #=========================
                            elif command == 'messagefriends':
                                if arguments:
                                    if logged_in[socket] in friends_list:
                                        for friend in friends_list[logged_in[socket]]:
                                            if friend in block_list and logged_in[socket] in block_list[friend]:
                                                pass
                                            else:
                                                # online message
                                                if friend in logged_in.values():
                                                    for user_socket, username in logged_in.items():
                                                        if username == friend:
                                                            user = user_socket
                                                    try:
                                                        socket.send('\r[Server] Message sent.\n')
                                                        user.send('\r[Private] ' + logged_in[socket] + ': ' + arguments + '\n')
                                                    except:
                                                        user.close()
                                                        connected.remove(socket)
                                                        del logged_in[user]

                                                # offline message
                                                else:
                                                    socket.send('\r[Server] Message sent.\n')
                                                    if friend in private_msgs:
                                                        private_msgs[friend].append('[Private] ' + logged_in[socket] + ': ' + arguments)
                                                    else:
                                                        private_msgs[friend] = ['[Private] ' + logged_in[socket] + ': ' + arguments]
                                    else: 
                                        socket.send('\r[Server] ERROR: There are no users in your friends list.\n')
                                else:
                                    socket.send('\r[Server] Usage: messagefriends <MESSAGE>\n')

                    except:
                        if socket in connected:
                            connected.remove(socket)
                        if socket in logged_in:
                            del logged_in[socket]
                        socket.close()

        server.close()
