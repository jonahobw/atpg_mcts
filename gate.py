import itertools
from typing import TypeVar, Generic

# needed because node and gate classes reference each other
GateType = TypeVar("GateType")

def generate_name(count):
    quot, rem = divmod(count - 1, 26)
    return generate_name(quot) + chr(rem + ord('A')) if count != 0 else ''


class Node:
    name_count = 0

    def __init__(self, name: str=None, gate_output: GateType=None, stuck_at=None):
        self.stuck_at = stuck_at
        self.state = 'X'
        self.gates = []  # gates for which this node is an input
        self.gate_output = gate_output  # gate for which this node is an output, None for PI
        if name is not None:
            self.name = name
        else:
            Node.name_count += 1
            self.name = generate_name(self.name_count)
        self.cc0 = None
        self.cc1 = None

    def set_controllability(self):
        """Return a tuple of CC0, CC1"""
        if self.is_pi():
            self.cc0 = 1
            self.cc1 = 1
            return 1, 1
        gate_type = self.gate_output.type
        gate_inputs = self.gate_output.inputs

        def xor_cc1_xnor_cc0(inputs):
            """
            Gets the xor cc1 and the equivalent xnor cc0
            = min(all combinations with odd number of 1's) + 1
            """
            def construct_odds(n):
                """
                Returns all combinations of n input variables with odd number of 1's.

                If a number is a 1, it is included in the result, else it is not
                included in the result and is assumed to be 0.

                Returned as a list of tuples.

                Examples:
                construct_odds(2) -> [(1), (2)]
                construct_odds(3) -> [(1), (2), (3), (1, 2, 3)]
                construct_odds(4) -> [(1), (2), (3), (4), (1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4)]

                :param n: number of input variables
                :return: a list of tuples
                """
                odds = [x for x in range(1, n + 1) if x % 2 == 1]

                res = []
                for odd in odds:
                    res.extend(list(itertools.combinations(range(1, n + 1), odd)))
                return res

            min = 1000000
            for combination in construct_odds(len(inputs)):
                term = 0
                for idx, input in enumerate(gate_inputs):
                    if idx + 1 in combination:
                        term += input.cc1
                    else:
                        term += input.cc0
                if term < min:
                    min = term
            return min + 1

        if gate_type == 'not':
            cc0 = gate_inputs[0].cc1 + 1
            cc1 = gate_inputs[0].cc0 + 1
        if gate_type == 'and':
            cc0 = min([x.cc0 for x in gate_inputs]) + 1
            cc1 = sum([x.cc1 for x in gate_inputs]) + 1
        if gate_type == 'nand':
            cc0 = sum([x.cc1 for x in gate_inputs]) + 1
            cc1 = min([x.cc0 for x in gate_inputs]) + 1
        if gate_type == 'or':
            cc0 = sum([x.cc0 for x in gate_inputs]) + 1
            cc1 = min([x.cc1 for x in gate_inputs]) + 1
        if gate_type == 'nor':
            cc0 = min([x.cc1 for x in gate_inputs]) + 1
            cc1 = sum([x.cc0 for x in gate_inputs]) + 1
        if gate_type == 'xor':
            cc0 = min([sum([x.cc0 for x in gate_inputs]), sum([x.cc1 for x in gate_inputs])]) + 1
            cc1 = xor_cc1_xnor_cc0(gate_inputs)
        if gate_type == 'xnor':
            cc0 = xor_cc1_xnor_cc0(gate_inputs)
            cc1 = min([sum([x.cc0 for x in gate_inputs]), sum([x.cc1 for x in gate_inputs])]) + 1
        self.cc0 = cc0
        self.cc1 = cc1
        return cc0, cc1

    def set_stuck_at(self, stuck_at):
        self.stuck_at = stuck_at
    
    def remove_fault(self):
        self.stuck_at = None
        self.state = 'X'
    
    def make_faulty(self, stuck_at: int, set: bool=False):
        self.stuck_at = stuck_at
        if set:
            self.activate_fault()

    def reset(self):
        self.state = 'X'

    def is_faulty(self):
        return self.stuck_at != None

    def is_fanout(self):
        return len(self.gates) > 1

    def set_state(self, val):
        if self.is_faulty() and val in ['D', '~D']:
            raise ValueError(f"Trying to assign {val} to a faulty gate {self}")
        if self.stuck_at == 0 and val == 1:
            self.state = 'D'
            return
        if self.stuck_at == 1 and val == 0:
            self.state = '~D'
            return
        self.state = val

    def activate_fault(self):
        if self.is_faulty():
            state = ['D', '~D']
            self.state = state[self.stuck_at]
    
    def is_fault_activated(self):
        if not self.is_faulty():
            raise ValueError("Calling node.is_fault_activated on non_faulty node.")
        state = ['D', '~D']
        return self.state == state[self.stuck_at]

    def is_po(self):
        return len(self.gates) == 0

    def has_x_path(self):
        """Returns true if there is a path with only X's from this node to a PO."""
        if self.is_po():
            return self.state == 'X'

        explored = []
        # list of gates which have state X
        to_explore = [gate.output for gate in self.gates if gate.output.state == 'X']
        while len(to_explore) > 0:
            node = to_explore.pop(-1)   # dfs
            explored.append(node)
            if node.is_po():
                return True
            for gate in node.gates:
                if gate.output.state == 'X':
                    to_explore.append(gate.output)
        return False

    def is_pi(self):
        return self.gate_output == None

    def __repr__(self):
        start = "^" if self.is_pi() else ""
        end = "$" if self.is_po() else ""
        return f"{start}{end}".ljust(1) + f"Node {self.name}".ljust(7) + ":" + f" {self.state}".rjust(3)


class Gate(Generic[GateType]):
    """
    Deals with 5 logic values:
    0, 1, X (undetermined), D (1 on good circuit, 0 on bad circuit) and ~D (not D)
    Inputs may have both X's and D's
    """
    name_counts = {
        "not": 0,
        "and": 0,
        "nand": 0,
        "or": 0,
        "nor": 0,
        "xor": 0,
        "xnor": 0
    }

    def __init__(self, type, *inputs: Node):
        self.control_value = -1     # will be set to 0 for and/nand, 1 for or/nor
        self.type = type
        Gate.name_counts[type] += 1
        self.name = f"{type}{Gate.name_counts[type]}"
        self.inputs = list(inputs)
        for node in self.inputs:
            node.gates.append(self)
        self.output = Node(gate_output=self)  # will get set after propagate() is called
        self.depth = self.set_depth()  # max number of gates between this one and PIs

    def set_depth(self):
        """
        Determines max number of gates between this one and primary inputs.  Used so that circuit
        propagation does not run into any dependency issues.

        Depth = max(depth of gates connected to inputs) + 1
        """
        depth = 0
        for input in self.inputs:
            if input.is_pi():
                continue
            # the input is the output of some gate
            if input.gate_output.depth > depth:
                depth = input.gate_output.depth
        return depth + 1

    def get_unassigned_inputs(self):
        return [node for node in self.inputs if node.state == 'X']

    def get_assigned_inputs(self):
        return [node for node in self.inputs if node.state != 'X']

    def get_hardest_controllable_input(self, val, unassigned=True):
        """Returns the input node to this gate that is the hardest to control.
        :param val: if 0, then get hardest cc0 controllability, else cc1
        """
        inputs = []
        if unassigned:
            inputs = self.get_unassigned_inputs()
        if len(inputs) == 0 or not unassigned:
            inputs = self.inputs
        maxm = 0
        node = None
        attribute = "cc0" if val == 0 else "cc1"
        for inp in inputs:
            controllability = getattr(inp, attribute)
            if controllability > maxm:
                node = inp
                maxm = controllability
        return node

    def get_easiest_controllable_input(self, val, unassigned=True):
        """Returns the input node to this gate that is the easiest to control.
        :param val: if 0, then get hardest cc0 controllability, else cc1
        """
        inputs = []
        if unassigned:
            inputs = self.get_unassigned_inputs()
        if len(inputs) == 0 or not unassigned:
            inputs = self.inputs

        minm = 100000
        node = None
        attribute = "cc0" if val == 0 else "cc1"
        for inp in inputs:
            controllability = getattr(inp, attribute)
            if controllability < minm:
                node = inp
                minm = controllability
        return node

    def is_on_d_frontier(self) -> bool:
        """In order to be true, the output must be X and there must be a D or ~D on the input."""
        if self.output.state != 'X':
            return False
        
        input_vals = [inp.state for inp in self.inputs]

        if 'D' in input_vals or '~D' in input_vals:
            return True
        return False

    def reset(self):
        for node in self.inputs:
            node.reset()
        self.output.reset()

    def propagate(self, verbose=False):
        """Propagate the current value of the gate's input Node to the output Node."""
        inputs = []
        for node in self.inputs:
            inputs.append(node.state)
        output = self._propagate(inputs)
        self.output.set_state(output)

        if verbose:
            print(self)
        return self.output.state

    def _propagate(self, inputs):
        """Calls appropriate function"""
        return getattr(self, f"{self.type}_propagate")(inputs)

    def invert(self, val):
        inverted = {
            'X': 'X',
            'D': '~D',
            '~D': 'D',
            0: 1,
            1: 0,
        }
        return inverted[val]

    def not_propagate(self, inputs):
        assert len(inputs) == 1
        return self.invert(inputs[0])

    def and_propagate(self, inputs):
        assert len(inputs) > 1

        if 0 in inputs: # at least one 0
            return 0

        if all([x == 1 for x in inputs]): # all 1's
            return 1

        # if we get to here, we know there are no 0's, just 1, X, D, ~D

        d_found = 'D' in inputs
        d_prime_found = '~D' in inputs

        if d_found and d_prime_found:
            return 0

        # if we get here, we know that there are not both D and ~D.  There also might be X's and 1's
        if 'X' in inputs:
            return 'X'

        if d_found and not d_prime_found:
            return 'D'
        if not d_found and d_prime_found:
            return '~D'

        return 0

    def or_propagate(self, inputs):
        assert len(inputs) > 1

        if 1 in inputs: # at least one 1
            return 1

        if not any(inputs): # all 0's
            return 0

        # if we get to here, we know there are no 1's, just 0, X, D, ~D

        d_found = 'D' in inputs
        d_prime_found = '~D' in inputs

        if d_found and d_prime_found:      # there is at least one 1
            return 1

        if 'X' in inputs:       # covers X's and D's or X's and ~D's
            return 'X'

        if d_found:     # covers D's
            return 'D'

        # covers ~D's
        return '~D'

    def nand_propagate(self, inputs):
        return self.invert(self.and_propagate(inputs))

    def nor_propagate(self, inputs):
        return self.invert(self.or_propagate(inputs))

    def xor_propagate(self, inputs):
        def xor_2inp(a, b):
            first_and = self.and_propagate([a, self.invert(b)])
            second_and = self.and_propagate([b, self.invert(a)])
            return self.or_propagate([first_and, second_and])

        val = inputs.pop(-1)

        while len(inputs) > 0:
            new_val = inputs.pop(-1)
            val = xor_2inp(val, new_val)

        return val

    def xnor_propagate(self, inputs):
        return self.invert(self.xor_propagate(inputs))

    def __repr__(self):
        return f"Gate {self.name}".ljust(12) + f"(depth {self.depth}):".ljust(13) + \
               f"{self.output}".ljust(13) + f" =   {self.type.upper()}".ljust(9) + f" {self.inputs}"


class Not(Gate):
    def __init__(self, *inputs):
        super().__init__("not", *inputs)


class And(Gate):
    def __init__(self, *inputs):
        super().__init__("and", *inputs)
        self.control_value = 0


class Or(Gate):
    def __init__(self, *inputs):
        super().__init__("or", *inputs)
        self.control_value = 1

class Nand(Gate):
    def __init__(self, *inputs):
        super().__init__("nand", *inputs)
        self.control_value = 0


class Nor(Gate):
    def __init__(self, *inputs):
        super().__init__("nor", *inputs)
        self.control_value = 1

class Xor(Gate):
    def __init__(self, *inputs):
        super().__init__("xor", *inputs)

class Xnor(Gate):
    def __init__(self, *inputs):
        super().__init__("xnor", *inputs)
