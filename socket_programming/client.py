import socket, select, sys

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print "Usage: python client.py <HOST> <PORT>"

    else:
        host = sys.argv[1]       # host IP
        port = int(sys.argv[2])  # port number

        #===================
        # Connect to server
        #===================
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host,port))

        #================
        # Authentication
        #================
        while True:
            data = s.recv(4096)

            # successful login
            if data[:7] == 'Success':
                print data
                break

            # print data from server and prompt
            else:
                sys.stdout.write(data)

                # error, exit program
                if data[:5] == 'ERROR':
                    sys.exit()

                msg = sys.stdin.readline()
                s.send(msg)
        sys.stdout.write('>> ')
        sys.stdout.flush()

        #===========================
        # Process data from sockets
        #===========================
        while True:
            read_sockets,write_sockets,error_sockets = select.select([sys.stdin, s],[],[])
            for socket in read_sockets:

                #==============
                # Receive data
                #==============
                if socket == s:
                    data = socket.recv(4096)
                    if not data:
                        print '\r[Server] ERROR: Disconnecting.\n'
                        sys.exit()
                    elif data == 'status_check':
                        pass
                    elif data == 'logout':
                        print '\r[Server] Successfully logged out.\n'
                        sys.exit()
                    elif data == 'time_logout':
                        print '\r[Server] You have been logged out due to inactivity.\n'
                        sys.exit()
                    else:
                        sys.stdout.write(data)
                        sys.stdout.write('>> ')
                        sys.stdout.flush()

                #===========
                # Send data
                #===========
                else:
                    msg = sys.stdin.readline()
                    s.send(msg)
                    sys.stdout.write('>> ')
                    sys.stdout.flush()