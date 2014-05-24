import sys
import socket
import select
import json
import threading
import time
import datetime
import copy
import os
import base64

#==============================================
# Sends this node's routing table to neighbors
#==============================================
def send_update():
    for neighbor in neighbors:
        neighbor_host, neighbor_port = neighbor.split(':')
        to_send = {
            'data_type': 'update',
            'routing_table': {}
        }
        for destination in routing_table:
            to_send['routing_table'][destination] = copy.deepcopy(routing_table[destination])

            # poison reverse
            if destination != neighbor and routing_table[destination]['next_hop'] == neighbor:
                to_send['routing_table'][destination]['cost'] = float('inf')
        s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))

#======================================================
# Thread for periodically sending updates to neighbors
#======================================================
def update_timer(interval):
    send_update()
    threading.Timer(interval, update_timer, [interval]).start()

#================================
# Thread for checking dead nodes
#================================
def node_timer():
    for neighbor in copy.deepcopy(neighbors):
        if neighbor in last_contact:
            if int(round(time.time() * 1000)) > last_contact[neighbor] + timeout*3000:
                if routing_table[neighbor]['cost'] != float('inf'):
                    routing_table[neighbor]['cost'] = float('inf')
                    routing_table[neighbor]['next_hop'] = ''
                    
                    del neighbors[neighbor]

                    # reinitialize routing table
                    for destination in routing_table:
                        if destination in neighbors:
                            routing_table[destination]['cost'] = direct_links[destination]
                            routing_table[destination]['next_hop'] = destination
                        else:
                            routing_table[destination]['cost'] = float('inf')
                            routing_table[destination]['next_hop'] = ''

                    to_send = {
                        'data_type': 'close',
                        'target': neighbor
                    }
                    for neighbor in neighbors:
                        neighbor_host, neighbor_port = neighbor.split(':')
                        s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                else:
                    send_update()
    threading.Timer(1, node_timer).start()

#====================
# Main program logic
#====================
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: python bfclient.py <CONFIG_FILE>'
    else:
        host = socket.gethostbyname(socket.gethostname())
        routing_table = {}
        neighbors = {}
        former_links = []
        direct_links = {}
        linkdowns = []
        last_contact = {}
        chunk1 = ''
        chunk2 = ''

        # parse information from config file
        file_name = sys.argv[1]
        with open(file_name) as config_file:
            first_line = config_file.readline()
            words = first_line.split()
            port = int(words[0])
            timeout = int(words[1])

            if len(words) > 2:
                file_chunk = words[2]
                file_seq_num = words[3]


            # string identifier for this node
            this_node = host + ':' + str(port)

            # initialize neighbors in routing table
            for line in config_file:
                words = line.split()
                neighbor = words[0]
                neighbor_cost = float(words[1])
                neighbors[neighbor] = {}
                routing_table[neighbor] = {}
                routing_table[neighbor]['cost'] = neighbor_cost
                routing_table[neighbor]['next_hop'] = neighbor
                direct_links[neighbor] = neighbor_cost

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((host, port))
        print '\nClient started.\nHOST: ' + host + ' | PORT: ' + str(port)
        print 'Initializing Bellman-Ford algorithm.\n'
        update_timer(timeout)
        node_timer()

        #==================================
        # listen for data from other nodes
        #==================================
        sys.stdout.write('>> ')
        sys.stdout.flush()
        while True:
            read_sockets,write_sockets,error_sockets = select.select([sys.stdin, s],[],[])
            for sock in read_sockets:
                if sock == s:
                    r, addr = sock.recvfrom(65536)
                    data = json.loads(r)
                    sender = addr[0] + ':' + str(addr[1])

                    #===============================
                    # receive: routing table update
                    #===============================
                    if data['data_type'] == 'update':
                        last_contact[sender] = int(round(time.time() * 1000))
                        table_changed = False

                        if routing_table[sender]['cost'] == float('inf'):
                            routing_table[sender]['cost'] = direct_links[sender]
                            routing_table[sender]['next_hop'] = sender
                            neighbors[sender] = {}
                            table_changed = True

                        # update neighbor's local routing table
                        neighbors[sender] = data['routing_table']

                        for node in data['routing_table']:
                            if node != this_node:

                                # newly discovered node
                                if node not in routing_table:
                                    routing_table[node] = {'cost': float('inf'), 'next_hop': ''}
                                    table_changed = True

                                # recalculate costs/next_hop to all destinations
                                for destination in routing_table:
                                    cost = routing_table[destination]['cost']
                                    if destination in neighbors[sender]:
                                        new_cost = routing_table[sender]['cost'] + neighbors[sender][destination]['cost']
                                        if new_cost < cost:
                                            routing_table[destination]['cost'] = new_cost
                                            routing_table[destination]['next_hop'] = sender
                                            table_changed = True

                        # if routing table changed, send update to neighbors
                        if table_changed:
                            send_update()
                            table_changed = False

                    #===================
                    # receive: linkdown
                    #===================
                    elif data['data_type'] == 'linkdown':
                        last_contact[sender] = int(round(time.time() * 1000))
                        pair = (str(data['pair'][0]), str(data['pair'][1]))
                        if pair in linkdowns:
                            send_update()
                        else:
                            linkdowns.append(pair)
                            if this_node == pair[1] and sender == pair[0]:
                                former_links.append(sender)
                                routing_table[sender]['cost'] = float('inf')
                                routing_table[sender]['next_hop'] = ''
                                del neighbors[sender]
                            
                            # reinitialize routing table
                            for destination in routing_table:
                                if destination in neighbors:
                                    routing_table[destination]['cost'] = direct_links[destination]
                                    routing_table[destination]['next_hop'] = destination
                                else:
                                    routing_table[destination]['cost'] = float('inf')
                                    routing_table[destination]['next_hop'] = ''

                            to_send = {
                                'data_type': 'linkdown',
                                'pair': pair,
                            }
                            for neighbor in neighbors:
                                neighbor_host, neighbor_port = neighbor.split(':')
                                s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                        
                    #=================
                    # receive: linkup
                    #=================
                    elif data['data_type'] == 'linkup':
                        last_contact[sender] = int(round(time.time() * 1000))
                        pair = data['pair']
                        new_weight = data['new_weight']
                        if (pair[0], pair[1]) in linkdowns:
                            linkdowns.remove((pair[0], pair[1]))
                            if this_node == pair[1] and sender == pair[0]:
                                former_links.remove(sender)
                                routing_table[sender]['cost'] = float(new_weight)
                                routing_table[sender]['next_hop'] = sender
                                neighbors[sender] = {}

                                to_send = {
                                    'data_type': 'linkup',
                                    'pair': pair,
                                    'new_weight': new_weight
                                }
                                for neighbor in neighbors:
                                    neighbor_host, neighbor_port = neighbor.split(':')
                                    s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                        elif (pair[1], pair[0]) in linkdowns:
                            linkdowns.remove((pair[1], pair[0]))
                            if this_node == pair[1] and sender == pair[0]:
                                former_links.remove(sender)
                                routing_table[sender]['cost'] = float(new_weight)
                                routing_table[sender]['next_hop'] = sender
                                neighbors[sender] = {}

                                to_send = {
                                    'data_type': 'linkup',
                                    'pair': pair,
                                    'new_weight': new_weight
                                }
                                for neighbor in neighbors:
                                    neighbor_host, neighbor_port = neighbor.split(':')
                                    s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                        else:
                            send_update()

                    #================
                    # receive: close
                    #================
                    elif data['data_type'] == 'close':
                        last_contact[sender] = int(round(time.time() * 1000))
                        target = data['target']
                        if routing_table[target]['cost'] != float('inf'):
                            routing_table[target]['cost'] = float('inf')
                            routing_table[target]['next_hop'] = ''
                            
                            if target in neighbors:
                                del neighbors[target]

                            # reinitialize routing table
                            for destination in routing_table:
                                if destination in neighbors:
                                    routing_table[destination]['cost'] = direct_links[destination]
                                    routing_table[destination]['next_hop'] = destination
                                else:
                                    routing_table[destination]['cost'] = float('inf')
                                    routing_table[destination]['next_hop'] = ''

                            to_send = {
                                'data_type': 'close',
                                'target': target
                            }
                            for neighbor in neighbors:
                                neighbor_host, neighbor_port = neighbor.split(':')
                                s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                        else:
                            send_update()

                    #===================
                    # receive: transfer
                    #===================
                    elif data['data_type'] == 'transfer':
                        destination_node = data['destination']
                        if this_node == destination_node:
                            print '\nTRANSFER: File chunk #' + str(data['seq_num']) + ' arrived here at destination.\nTimestamp: ' + str(datetime.datetime.now()) + '\nPath: ' + data['path'] + ' -> ' + this_node
                            
                            if(int(data['seq_num']) == 1):
                                chunk1 = data['file_data'].decode('base64')
                            if(int(data['seq_num']) == 2):
                                chunk2 = data['file_data'].decode('base64')

                            if chunk1 and chunk2:
                                output_file = open('output', 'wb')
                                output_file.write(chunk1)
                                output_file.write(chunk2)
                                output_file.close()
                                print 'Combined file written to output.'

                            print ''
                            sys.stdout.write('>> ')
                            sys.stdout.flush()

                        else:
                            print '\nTRANSFER: File chunk #' + str(data['seq_num']) + ' arrived.'
                            next_hop = routing_table[destination_node]['next_hop']
                            next_host, next_port = next_hop.split(':')

                            new_path = data['path'] + ' -> ' + this_node

                            to_send = {
                                'data_type': 'transfer',
                                'destination': destination_node,
                                'file_data': data['file_data'],
                                'seq_num': data['seq_num'],
                                'path': new_path
                            }
                            s.sendto(json.dumps(to_send), (next_host,int(next_port)))
                            print 'TRANSFER: File chunk #' + str(data['seq_num']) + ' sent to next node: ' + next_hop + '\n'
                            sys.stdout.write('>> ')
                            sys.stdout.flush()

                #==========
                # commands
                #==========
                else:
                    data = sys.stdin.readline()

                    data_split = data.split(' ',1)
                    command = data_split[0].rstrip()
                    if len(data_split) > 1:
                        arguments = data_split[1]
                    else:
                        arguments = ''

                    #=================
                    # command: SHOWRT
                    #=================
                    if command.lower() == 'showrt':
                        for destination in routing_table:
                            print 'Destination = ' + destination + ', Cost = ' + str(routing_table[destination]['cost']) + ', Link = ' + routing_table[destination]['next_hop']
                        print ''

                    #===================
                    # command: LINKDOWN
                    #===================
                    elif command.lower() == 'linkdown':
                        arguments_split = arguments.split(' ')
                        if len(arguments_split) != 2:
                            print 'ERROR: Incorrect number of arguments.\n'
                        else:
                            target_host = arguments_split[0]
                            target_port = arguments_split[1]
                            target_node = (target_host + ':' + str(target_port)).rstrip()

                            if target_node not in neighbors:
                                print 'ERROR: Target node is not a neighbor.\n'
                            else:
                                former_links.append(target_node)
                                del neighbors[target_node]

                                # reinitialize routing table
                                for destination in routing_table:
                                    if routing_table[destination]['next_hop'] == target_node:
                                        if destination in neighbors:
                                            routing_table[destination]['cost'] = direct_links[destination]
                                            routing_table[destination]['next_hop'] = destination
                                        else:
                                            routing_table[destination]['cost'] = float('inf')
                                            routing_table[destination]['next_hop'] = ''

                                pair = (this_node, target_node)
                                linkdowns.append(pair)

                                to_send = {
                                    'data_type': 'linkdown',
                                    'pair': pair,
                                }
                                for neighbor in neighbors:
                                    neighbor_host, neighbor_port = neighbor.split(':')
                                    s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                                s.sendto(json.dumps(to_send), (target_host,int(target_port)))

                    #=================
                    # command: LINKUP
                    #=================
                    elif command.lower() == 'linkup':
                        arguments_split = arguments.split(' ')
                        if len(arguments_split) != 3:
                            print 'ERROR: Incorrect number of arguments.\n'
                        else:
                            target_host = arguments_split[0]
                            target_port = arguments_split[1]
                            target_node = (target_host + ':' + str(target_port)).rstrip()
                            new_weight = arguments_split[2]
                            
                            if target_node not in former_links:
                                print 'ERROR: Invalid link.\n'
                            else:
                                former_links.remove(target_node)
                                routing_table[target_node]['cost'] = float(new_weight)
                                routing_table[target_node]['next_hop'] = target_node
                                neighbors[target_node] = {}

                                if (target_node, this_node) in linkdowns:
                                    linkdowns.remove((target_node, this_node))
                                elif (this_node, target_node) in linkdowns:
                                    linkdowns.remove((this_node, target_node))

                                to_send = {
                                    'data_type': 'linkup',
                                    'pair': (this_node, target_node),
                                    'new_weight': new_weight
                                }
                                for neighbor in neighbors:
                                    neighbor_host, neighbor_port = neighbor.split(':')
                                    s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))

                    #================
                    # command: CLOSE
                    #================
                    elif command.lower() == 'close':
                        to_send = {
                            'data_type': 'close',
                            'target': this_node
                        }
                        for neighbor in neighbors:
                            neighbor_host, neighbor_port = neighbor.split(':')
                            s.sendto(json.dumps(to_send), (neighbor_host,int(neighbor_port)))
                        os._exit(1)

                    #===================
                    # command: TRANSFER
                    #===================
                    elif command.lower() == 'transfer':
                        arguments_split = arguments.split(' ')
                        if len(arguments_split) != 2:
                            print 'ERROR: Incorrect number of arguments.\n'
                        elif not file_chunk:
                            print 'ERROR: This is not a valid source node.\n'
                        else:
                            destination_host = arguments_split[0]
                            destination_port = arguments_split[1]
                            destination_node = (destination_host + ':' + str(destination_port)).rstrip()

                            next_hop = routing_table[destination_node]['next_hop']
                            next_host, next_port = next_hop.split(':')

                            file_data = ''
                            with open(file_chunk, 'rb') as f:
                                file_data = base64.b64encode(f.read())

                            to_send = {
                                'data_type': 'transfer',
                                'destination': destination_node,
                                'file_data': file_data,
                                'seq_num': file_seq_num,
                                'path': this_node
                            }
                            s.sendto(json.dumps(to_send), (next_host,int(next_port)))

                            print 'TRANSFER: File chunk #' + str(file_seq_num) + ' sent to next node: ' + next_hop + '\n'

                    sys.stdout.write('>> ')
                    sys.stdout.flush()
                    