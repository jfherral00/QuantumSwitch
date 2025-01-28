Configuration file
===================
The configuration file must be named *properties.cfg* and must be placed in the same directory as the Python source code.
See examples in [examples](../examples/).

The following parameters must be specified:

Simulation
---------------
- *duration*: duration of the simulation (nanoseconds)

Network topology
----------------
- *list_sw_table*: list of lists of pairs that want to share entanglement.
- *num_leaves*: number of nodes connected to the switch
- *list_distance*: list of distances between end nodes and switch to be simulated (km)

Memory parameters
----------------
- *T1*: T1 time, dictating amplitude damping component for memories (nanoseconds)
- *T2*: T2 dephasing time for memories (nanoseconds)

Quantum processors
----------------
- *dephase_rate*: Dephasing rate in gates (Hz)
- *list_instr*: list of duration of operations in gates (nanoseconds)

Quantum sources
----------------
- *source_fidelity_sq*: Fidelity of the source

Depolarizing channels
----------------
- *p_depol_init*: Probability of depolarization on entering a fibre
- *p_depol_length*: Probability of depolarization per km of fibre

