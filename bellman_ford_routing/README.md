CSEE W4119 Computer Networks<br/>
Programming Assignment #2: Bellman Ford Routing

Assignment
----------
The purpose of this assignment was to implement the Bellman Ford routing algorithm over a distributed system. Additionally, the routing table generated from this algorithm was used to send two file chunks from different starting nodes to a single destination node.  

Running
-------
The program is written in Python version 2.7. To run, each client should run:
>python bfclient.py <CONFIG_FILE>

Each node/client has its own config file that is consistent with all others. Ensure that the config file is in the same directory as 'bfclient.py'.

Description
-----------
Nodes communicate with neighbors through UDP; the routing tables at each node will converge some time after every node has run the program. A command line is also provided to each client. The commands supported are described in the assignment, provided in 'assignment.pdf'. See this file for more information on the file transfer as well. Sample file chunks and config files have been included, but note that the IP addresses and ports will have to be changed to correspond to the client machines.