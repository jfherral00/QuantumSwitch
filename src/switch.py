import random
from netsquid.nodes import Node

class Switch(Node):
    def __init__(self,name,qmemory):
        self._swap_queue = []
        super().__init__(name,qmemory=qmemory)
        self._solved_conflicts = 0
        
    def add_request(self,request):
        '''
        Receives the protocol that wants to perform the Bell measurement
        Input:
            - request: name of th requestor protocol (string)
        Output:
            No output
        '''
        self._swap_queue.append(request)
        
    def get_request(self,strategy):
        '''
        Retrieve an operation to execute from the queue.
        Can be the first one or the last one
        Input:
            - strategy: if first in queue should be returned, last or random (first|last|random)
        Output:
            - protocol_name: name of the protocol for which the entanglement will be executed
        '''
        if strategy == 'FIFO':
            protocol_name = self._swap_queue[0]
        elif strategy == 'LIFO':
            protocol_name = self._swap_queue[-1]
        else:
            protocol_name = random.choice(self._swap_queue)
            
        return(protocol_name)
    
    def remove_request(self,request):
        '''
        Delete an operation from the queue.
        Can be the first one or the last one
        Input:
            - request: name of the SwapProtocol to be removed.
        Output:
            No output
        '''
        
        position = self._swap_queue.index(request)
        self._swap_queue.pop(position)
        
    def get_solved_conflicts(self):
        '''
        Returns the number of solved conflicts
        Output:
            - _solved_conflicts: number of solved conflicts
        '''
        return self._solved_conflicts
    
    def increase_solved_conflicts(self):
        '''
        Increases the number of solved conflicts by one
        Output:
            No output
        '''
        self._solved_conflicts += 1

    