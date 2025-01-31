
import pandas
import pydynaa
import numpy as np
from icecream import ic

import netsquid as ns
from utils import readProperties
from netsquid.nodes import Node, Connection, Network
#from netsquid.protocols.protocol import Signals
from netsquid.protocols import LocalProtocol, NodeProtocol, Signals
from netsquid.protocols.nodeprotocols import NodeProtocol
from netsquid.qubits import ketstates as ks
from netsquid.components import Message, QuantumProcessor, QuantumProgram, PhysicalInstruction
from netsquid.components.models.qerrormodels import DepolarNoiseModel, DephaseNoiseModel, QuantumErrorModel
from netsquid.components.instructions import INSTR_MEASURE_BELL, INSTR_X, INSTR_Z
from netsquid.examples.teleportation import ClassicalConnection
from netsquid.util.datacollector import DataCollector
from netsquid.components.models.qerrormodels import T1T2NoiseModel
from netsquid.components.qchannel import QuantumChannel
#from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.qsource import QSource, SourceStatus
from netsquid.qubits.state_sampler import StateSampler
from netsquid.components.models.delaymodels import FibreDelayModel, FixedDelayModel
import warnings

#Ignore deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


class EntanglingConnection(Connection):
    """A connection that generates entanglement.

    Consists of a midpoint holding a quantum source that connects to
    outgoing quantum channels.

    Parameters
    ----------
    length : float
        End to end length of the connection [km].
    source_fidelity_sq : float
        Source fidelity.
    name : str, optional
        Name of this connection.

    """

    def __init__(self, length, source_fidelity_sq, name="EntanglingConnection"):
        super().__init__(name=name)
        qsource = QSource(f"qsource_{name}", StateSampler([ks.b00,ks.s00], [source_fidelity_sq,(1-source_fidelity_sq)]), num_ports=2,
                          status=SourceStatus.EXTERNAL,
                          models={"emission_delay_model": FixedDelayModel(delay=0)})
        self.add_subcomponent(qsource, name="qsource")
        qchannel_c2a = QuantumChannel("qchannel_C2A", length=length / 2,
                                      models={"delay_model": FibreDelayModel()})
        qchannel_c2b = QuantumChannel("qchannel_C2B", length=length / 2,
                                      models={"delay_model": FibreDelayModel()})
        # Add channels and forward quantum channel output to external port output:
        self.add_subcomponent(qchannel_c2a, forward_output=[("A", "recv")])
        self.add_subcomponent(qchannel_c2b, forward_output=[("B", "recv")])
        # Connect qsource output to quantum channel input:
        try:
            qsource.ports["qout0"].connect(qchannel_c2a.ports["send"])
            qsource.ports["qout1"].connect(qchannel_c2b.ports["send"])
        except:
            pass

class FibreDepolarizeModel(QuantumErrorModel):
    """Custom non-physical error model used to show the effectiveness
    of repeater chains.

    The default values are chosen to make a nice figure,
    and don't represent any physical system.

    Parameters
    ----------
    p_depol_init : float, optional
        Probability of depolarization on entering a fibre.
        Must be between 0 and 1. Default 0.009
    p_depol_length : float, optional
        Probability of depolarization per km of fibre.
        Must be between 0 and 1. Default 0.025

    """
    def __init__(self, p_depol_init=0.09, p_depol_length=0.025):
        super().__init__()
        self.properties['p_depol_init'] = p_depol_init
        self.properties['p_depol_length'] = p_depol_length
        self.required_properties = ['length']

    def error_operation(self, qubits, delta_time=0, **kwargs):
        """Uses the length property to calculate a depolarization probability,
        and applies it to the qubits.

        Parameters
        ----------
        qubits : tuple of :obj:`~netsquid.qubits.qubit.Qubit`
            Qubits to apply noise to.
        delta_time : float, optional
            Time qubits have spent on a component [ns]. Not used.

        """
        for qubit in qubits:
            prob = 1 - (1 - self.properties['p_depol_init']) * np.power(
                10, - kwargs['length']**2 * self.properties['p_depol_length'] / 10)
            ns.qubits.depolarize(qubit, prob=prob)
            
class ControlProtocol(LocalProtocol):
    '''
    One LocalProtocol controlls every SwapProtocol and CorrectProtocol
    Parameters
    ----------
    network : instance of the network that has been created
    switching_table: list of tuples
        Switching table
    name: optional name of the protocol
    '''
    def __init__(self, network, switching_table, name=None):
        self._network = network
        self._switching_table = switching_table
        name = name if name else f"ControlProtocol"
        super().__init__(nodes=network.nodes)
        
        #Initialize start expression
        self.start_expression = None
        
        nodes = [network.nodes[name] for name in sorted(network.nodes.keys())]
        
        # Add SwapProtocol to conigured pairs in Switch. Note: we use unique names,
        # since the subprotocols would otherwise overwrite each other in the main protocol.
        switch = network.nodes["Switch"]
        for route in switching_table:
            subprotocol = SwapProtocol(node=switch, origin=route[0], destination=route[1])
            self.add_subprotocol(subprotocol)
            node = nodes[route[1]-1]
            subprotocol = CorrectProtocol(node=node, name=f"Correct_{route[1]}",origin =route[0], destination=route[1],network=network)
            self.add_subprotocol(subprotocol)
            self.start_expression = self.start_expression | self.await_signal(subprotocol, Signals.SUCCESS)
    
    def run(self):
        self.start_subprotocols()
        
        #Initial trigger in ALL entangling connections
        for conn in self._network.connections:
            for route in self._switching_table:
                left = "left-" + str(route[0]) + "-switch"
                right = "switch-node" + str(route[1]) + "-quantum"
                if  left in conn:
                    entconn = network.subcomponents[conn]
                    qs1 = entconn.subcomponents["qsource"]
                    qs1.trigger()
                if right in conn:
                    entconn = network.subcomponents[conn]
                    qs1 = entconn.subcomponents["qsource"]
                    qs1.trigger()
        
        while True:
            #Wait for entanglement to be completed in any communication
            evexpr = yield self.start_expression
            
            
            #Send signal to data collector
            protocol = evexpr.triggered_events[-1].source
            result = protocol.get_signal_result(Signals.SUCCESS)
            self.send_signal(Signals.SUCCESS,[result[0], result[1]])
            
            #Signal qsources for new entanglement
            for conn in self._network.connections:
                left = "left-" + str(result[0]) + "-switch"
                right = "switch-node" + str(result[1]) + "-quantum"
                if  left in conn:
                    entconn = network.subcomponents[conn]
                    qs1 = entconn.subcomponents["qsource"]
                    qs1.trigger()
                if right in conn:
                    entconn = network.subcomponents[conn]
                    qs1 = entconn.subcomponents["qsource"]
                    qs1.trigger()

class SwapProtocol(NodeProtocol):
    """Perform Swap on a switch node.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node` or None, optional
        Node this protocol runs on.
    origin : int
        Origin node.
    destination : int
        Destination node
    """

    def __init__(self, node, origin, destination):
        name = f"SwapProtocol{origin}_{destination}"
        self._origin = origin
        self._destination = destination
        super().__init__(node, name)
        self._qmem_input_port_l = self.node.qmemory.ports[f"qin{origin}"]
        self._qmem_input_port_r = self.node.qmemory.ports[f"qin{destination}"]
        self._program = QuantumProgram(num_qubits=2)
        q1, q2 = self._program.get_qubit_indices(num_qubits=2)
        self._program.apply(INSTR_MEASURE_BELL, [q1, q2], output_key="m", inplace=False)

    def run(self):
        while True:
            yield (self.await_port_input(self._qmem_input_port_l) &
                   self.await_port_input(self._qmem_input_port_r))   
            request_stack.append(self._origin)  
            
            not_serviced = True
            
            if self.node.qmemory.busy:
                yield self.await_program(self.node.qmemory)
            
            while not_serviced:
                if request_stack[0] == self._origin:
                    yield self.node.qmemory.execute_program(self._program, qubit_mapping=[self._destination,self._origin])
                    request_stack.pop(0)
                    m, = self._program.output["m"]
                    # Send result to right node on end
                    self.node.ports[f"ccon_R{self._destination}"].tx_output(Message(m))
                    not_serviced = False
                else:
                    yield self.await_timer(duration=100) #Nothing to do, just wait

class SwapCorrectProgram(QuantumProgram):
    """Quantum processor program that applies all swap corrections."""
    default_num_qubits = 1

    def set_corrections(self, x_corr, z_corr):
        self.x_corr = x_corr % 2
        self.z_corr = z_corr % 2

    def program(self):
        q1, = self.get_qubit_indices(1)
        if self.x_corr == 1:
            self.apply(INSTR_X, q1)
        if self.z_corr == 1:
            self.apply(INSTR_Z, q1)
        yield self.run()


class CorrectProtocol(NodeProtocol):
    """Perform corrections for a swap on an end-node.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node` or None, optional
        Node this protocol runs on.
    name: str, optional
    origin : int
        Origin node.
    destination : int
        Destination node

    """
    def __init__(self, node, name, origin, destination,network):
        super().__init__(node, name)
        self._origin = origin
        self._destination = destination
        self.num_nodes = 3
        self._x_corr = 0
        self._z_corr = 0
        self._program = SwapCorrectProgram()
        self._counter = 0

    def run(self):
        while True:
            yield self.await_port_input(self.node.ports["ccon_L"])
            message = self.node.ports["ccon_L"].rx_input()
            if message is None or len(message.items) != 1:
                continue
            m = message.items[0]
            if m == ks.BellIndex.B01 or m == ks.BellIndex.B11:
                self._x_corr += 1
            if m == ks.BellIndex.B10 or m == ks.BellIndex.B11:
                self._z_corr += 1
            self._counter += 1
            if self._counter == self.num_nodes - 2:
                if self._x_corr or self._z_corr:
                    self._program.set_corrections(self._x_corr, self._z_corr)
                    #if self.node.qmemory.busy:
                    #    yield self.await_program(self.node.qmemory)

                    yield self.node.qmemory.execute_program(self._program, qubit_mapping=[0])
                    
                self.send_signal(Signals.SUCCESS,[self._origin, self._destination])
                self._x_corr = 0
                self._z_corr = 0
                self._counter = 0

def create_qprocessor(name,num_leaves,instr_duration):
    """Factory to create a quantum processor for each node in the repeater chain network.

    Has two memory positions and the physical instructions necessary for teleportation.

    Parameters
    ----------
    name : str
        Name of the quantum processor.
    num_leaves : int
        number of connected nodes
    instr_duration : int,
        Duration of gate operations    

    Returns
    -------
    :class:`~netsquid.components.qprocessor.QuantumProcessor`
        A quantum processor to specification.

    """
    T1 = cfg['t1']
    T2 = cfg['t2']
    dephase_rate = cfg['dephase_rate']
    gate_duration = instr_duration
    gate_noise_model = DephaseNoiseModel(dephase_rate)
    mem_noise_model = T1T2NoiseModel(T1=T1,T2=T2)
    physical_instructions = [
        PhysicalInstruction(INSTR_X, duration=gate_duration,
                            quantum_noise_model=gate_noise_model),
        PhysicalInstruction(INSTR_Z, duration=gate_duration,
                            quantum_noise_model=gate_noise_model),
        PhysicalInstruction(INSTR_MEASURE_BELL, duration=gate_duration,
                            quantum_noise_model=gate_noise_model),
    ]
    qproc = QuantumProcessor(name, num_positions=num_leaves+1, fallback_to_nonphysical=False,
                             mem_noise_models=[mem_noise_model] * (num_leaves+1),
                             phys_instructions=physical_instructions)
    return qproc


def build_network(num_leaves, link_distance,source_fidelity_sq,switching_table,instr_duration):
    """Setup repeater chain network.

    Parameters
    ----------
    num_leaves : int
        Number of links, at least 2.
    link_distance : float
        Distance between nodes [km].
    source_fidelity_sq : float
        Source fidelity.
    switching_table: list of tuples
        Switching table
    instr_duration : int,
        Duration of gate operations

    Returns
    -------
    :class:`~netsquid.nodes.network.Network`
        Network component with all nodes and connections as subcomponents.

    """
    if num_leaves < 2:
        raise ValueError(f"Can't create switch with {num_leaves} nodes.")
    network = Network("Simple Switch")

    #Create Switch with num_leaves quantum processors
    switch = Node(f"Switch", qmemory=create_qprocessor(f"qproc_switch",num_leaves,instr_duration))
    # Create nodes with quantum processors
    nodes = []
    nodes.append(switch)

    for i in range(1,num_leaves+1):
        # Prepend leading zeros to the number
        num_zeros = int(np.log10(num_leaves+1)) + 1
        nodes.append(Node(f"Node_{i:0{num_zeros}d}", qmemory=create_qprocessor(f"qproc_{i}",1,instr_duration)))
    network.add_nodes(nodes)
    # Create quantum and classical connections between links in switching table:
    for route in switching_table:
        nodeA, nodeB = nodes[route[0]], nodes[route[1]]
        #Create EntanglingConnection in both links
        # Setup entangling connection between nodes:
        qconn = EntanglingConnection(name=f"left-{route[0]}-switch", length=link_distance,
                                     source_fidelity_sq=source_fidelity_sq)
        qconn2 = EntanglingConnection(name=f"right-switch-{route[1]}", length=link_distance,
                                     source_fidelity_sq=source_fidelity_sq)
        #Add noise model to quantum channels
        for channel_name in ['qchannel_C2A', 'qchannel_C2B']:
            qconn.subcomponents[channel_name].models['quantum_noise_model'] =\
                FibreDepolarizeModel(p_depol_init=cfg['p_depol_init'], p_depol_length=cfg['p_depol_length'])
            qconn2.subcomponents[channel_name].models['quantum_noise_model'] =\
                FibreDepolarizeModel(p_depol_init=cfg['p_depol_init'], p_depol_length=cfg['p_depol_length'])

        #Connect entangling souce to left node and switch  
        port_name, port_r_name = network.add_connection(
            nodeA, switch, connection=qconn, label=f"left-{route[0]}-switch")
        # Forward qconn directly to quantum memories for right and left inputs:
        nodeA.ports[port_name].forward_input(nodeA.qmemory.ports["qin0"])  # left node
        switch.ports[port_r_name].forward_input(
            switch.qmemory.ports[f"qin{route[0]}"])  # right node
        
        #Connect entangling souce to right node and switch  
        port_name, port_r_name = network.add_connection(
            switch, nodeB, connection=qconn2, label=f"switch-node{route[1]}-quantum")
        # Forward qconn directly to quantum memories for right and left inputs:
        nodeB.ports[port_r_name].forward_input(nodeB.qmemory.ports["qin0"])  # right node
        switch.ports[port_name].forward_input(
            switch.qmemory.ports[f"qin{route[1]}"])  #left node
        
        # Create classical connection from switch to right node
        cconn = ClassicalConnection(name=f"cconn_switch-node{route[1]}", length=link_distance)
        port_name, port_r_name = network.add_connection(
            switch, nodeB, connection=cconn, label="classical",
            port_name_node1=f"ccon_R{route[1]}", port_name_node2="ccon_L")
        
    return network


def setup_datacollector(network, control_protocol, switching_table):
    """Setup the datacollector to calculate the fidelity
    when the CorrectionProtocol has finished.

    Parameters
    ----------
    network : :class:`~netsquid.nodes.network.Network`
        Repeater chain network to put protocols on.

    protocol : :class:`~netsquid.protocols.protocol.Protocol`
        Protocol holding all subprotocols used in the network.
    
    switching_table: list of tuples
        Switching table

    Returns
    -------
    :class:`~netsquid.util.datacollector.DataCollector`
        Datacollector recording fidelity data.

    """
    # Ensure nodes are ordered in the chain:
    nodes = [network.nodes[name] for name in sorted(network.nodes.keys())]

    def calc_fidelity(evexpr):
        protocol = evexpr.triggered_events[-1].source
        result = protocol.get_signal_result(Signals.SUCCESS)
        qubit_a, = nodes[result[0]-1].qmemory.peek([0])
        qubit_b, = nodes[result[1]-1].qmemory.peek([0])
        fidelity = ns.qubits.fidelity([qubit_a, qubit_b], ks.b00, squared=True)
        return {"F2": fidelity,
                "links": str(result[0])+"-"+str(result[1])}

    dc = DataCollector(calc_fidelity, include_entity_name=False)
    dc.collect_on(pydynaa.EventExpression(source=control_protocol,event_type=Signals.SUCCESS.value))

    return dc

########################            Main program         ################################
#Read properties
cfg = {}
readProperties(cfg,'./properties.cfg','SimpleSwitch')
df_csv = pandas.DataFrame(columns=['#Demands','Distance','Instr_time','Fidelity','#EPRs','Time'])
for switching_table in cfg['list_sw_table']:
    ic(switching_table)
    for instr in cfg['list_instr']:
        ic(instr)
        for distance in cfg['list_distance']:
            ic(distance)
            #This stack will store the requests that want to use entanglement. Will be managed as FIFO
            request_stack = []

            network = build_network(num_leaves=cfg['num_leaves'],link_distance=distance, 
                                    source_fidelity_sq=cfg['source_fidelity_sq'], 
                                    switching_table=switching_table,instr_duration=instr)

            control_protocol = ControlProtocol(network=network,switching_table=switching_table,name=ControlProtocol)
            dc = setup_datacollector(network,control_protocol,switching_table)

            control_protocol.start()

            ns.sim_run(duration=cfg['duration'])
            
            #If fidelity of entangled pair is below 0.95, entanglement swap has failed
            dfSwapOK = dc.dataframe[dc.dataframe['F2']>0.95]

            df_agrupado = dfSwapOK.groupby('links')

            df_data = pandas.DataFrame()
            df_data['Fidelity'] = df_agrupado["F2"].mean()
            df_data['#EPRs'] = df_agrupado['F2'].count()

            for path in df_data.index.to_list():
                df_data.at[path,'Avg_time'] = dc.dataframe[dc.dataframe['links']==path]['time_stamp'].diff().mean()

            print("Average fidelity, #EPRs and Avg_time of generated entanglement via a switch:\n {}".format(df_data))
            df_temp = pandas.DataFrame({
                '#Demands': [len(df_data)],
                'Distance': distance,
                'Instr_time': instr,
                'Fidelity': [df_data['Fidelity'].mean()],
                '#MeanEPRsPerDemand': [df_data['#EPRs'].mean()],
                '#TotalEPRs': [df_data['#EPRs'].sum()],
                'Time': [df_data['Avg_time'].mean()]}
            )
            df_csv = pandas.concat([df_csv,df_temp], axis=0, ignore_index=True)
            
            ns.sim_stop()
            ns.sim_reset()

df_csv.to_csv('./results.csv', index=False)    
    
    
#print("Average fidelity of generated entanglement via a switch:\n {}".format(df_agrupado["F2"].mean()))
#print('The number of entangled pairs by path were:\n {}'.format(df_agrupado['F2'].count()))
#In order to calculate average entanglement time for link 1-2 uncomment below
#print(dc.dataframe[dc.dataframe['links']=='1-2']['time_stamp'].diff().mean())

