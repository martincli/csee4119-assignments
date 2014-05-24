CSEE W4119 Computer Networks<br/>
Programming Assignment #1: Socket Programming

Assignment
----------
The purpose of this assignment was to implement a simple client-server chatroom using TCP (multiple clients connecting to single server). Features include basic authentication and private messaging.

Running
-------
The program is written in Python version 2.7. To run, first start the server:
>python server.py <PORT>

Connect to server:
>python client.py <HOST> <PORT>

Ensure that 'user_pass.txt' is in the same directory as 'server.py'.

Description
-----------
The commands supported are described in the assignment, provided in 'assignment.pdf'.

For extra credit, basic friends list functionality was also added:
- addfriend <USER>: adds user to friends list (error if user does not exist or is already on friends list)
- removefriend <USER>: removes user from friends list (error if user is not a friend)
- viewfriends: displays friends list 
- messagefriends <MESSAGE>: messages all users on friends list (private message, online/offline functionality is the same as the message command)
