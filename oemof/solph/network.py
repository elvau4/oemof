# -*- coding: utf-8 -*-
""" Classes used to model energy supply systems within solph.

Classes are derived from oemof core network classes and adapted for specific
optimization tasks. An energy system is modelled as a graph/network of nodes
with very specific constraints on which types of nodes are allowed to be
connected.
"""

import warnings
import oemof.network as on
import oemof.energy_system as es
from .plumbing import sequence


class EnergySystem(es.EnergySystem):
    """ A variant of :class:`EnergySystem
    <oemof.core.energy_system.EnergySystem>` specially tailored to solph.

    In order to work in tandem with solph, instances of this class always use
    :const:`solph.GROUPINGS <oemof.solph.GROUPINGS>`. If custom groupings are
    supplied via the `groupings` keyword argument, :const:`solph.GROUPINGS
    <oemof.solph.GROUPINGS>` is prepended to those.

    If you know what you are doing and want to use solph without
    :const:`solph.GROUPINGS <oemof.solph.GROUPINGS>`, you can just use
    :class:`core's EnergySystem <oemof.core.energy_system.EnergySystem>`
    directly.
    """

    def __init__(self, **kwargs):
        # Doing imports at runtime is generally frowned upon, but should work
        # for now. See the TODO in :func:`constraint_grouping
        # <oemof.solph.groupings.constraint_grouping>` for more information.
        from . import GROUPINGS
        from .custom import custom_grouping
        kwargs['groupings'] = (GROUPINGS +
                               [custom_grouping] +
                               kwargs.get('groupings', []))
        super().__init__(**kwargs)


class Flow:
    r""" Defines a flow between two nodes.

    Keyword arguments are used to set the attributes of this flow. Parameters
    which are handled specially are noted below.
    For the case where a parameter can be either a scalar or a sequence, a
    scalar value will be converted to a sequence containing the scalar value at
    every index. This sequence is then stored under the paramter's key.

    Parameters
    ----------
    nominal_value : numeric
        The nominal value of the flow. If this value is set the corresponding
        optimization variable of the flow object will be bounded by this value
        multiplied with min(lower bound)/max(upper bound).
    min : numeric (sequence or scalar)
        Normed minimum value of the flow. The flow absolute maximum will be
        calculated by multiplying :attr:`nominal_value` with :attr:`min`
    max : numeric (sequence or scalar)
        Nominal maximum value of the flow. (see. :attr:`min`)
    actual_value: numeric (sequence or scalar)
        Specific value for the flow variable. Will be multiplied with the
        nominal\_value to get the absolute value. If fixed attr is set to True
        the flow variable will be fixed to actual_value * :attr:`nominal_value`
        , I.e. this value is set exogenous.
    positive_gradient : numeric (sequence or scalar)
        The normed maximal positive difference (flow[t-1] < flow[t])
        of two consecutive flow values.
    negative_gradient : numeric (sequence or scalar)
        The normed maximum negative difference (from[t-1] > flow[t]) of two
        consecutive timesteps.
    summed_max : numeric
        Specific maximum value summed over all timesteps. Will be multiplied
        with the nominal_value to get the absolute limit.
    summed_min : numeric
        see above
    variable_costs : numeric (sequence or scalar)
        The costs associated with one unit of the flow. If this is set the
        costs will be added to the objective expression of the optimization
        problem.
    fixed_costs : numeric
        The costs of the whole period associated with the absolute
        nominal_value of the flow.
    fixed : boolean
        Boolean value indicating if a flow is fixed during the optimization
        problem to its ex-ante set value. Used in combination with the
        :attr:`actual_value`.
    investment : :class:`oemof.solph.options.Investment` object
        Object indicating if a nominal_value of the flow is determined by
        the optimization problem. Note: This will refer all attributes to an
        investment variable instead of to the nominal_value. The nominal_value
        should not be set (or set to None) if an investment object is used.
    binary :  :class:`oemof.solph.options.BinaryFlow` object
        If an binary flow object is added here, the flow constraints will
        be altered significantly as the mathematical model for the flow
        will be different, i.e. constraint etc from
        :class:`oemof.solph.blocks.BinaryFlow` will be used instead of
        :class:`oemof.solph.blocks.Flow`. Note: this does not work in
        combination with the investment attribute set at the moment.

    Notes
    -----
    The following sets, variables, constraints and objective parts are created
     * :py:class:`~oemof.solph.blocks.Flow`
     * :py:class:`~oemof.solph.blocks.InvestmentFlow` (additionally if
       Investment object is present)
     * :py:class:`~oemof.solph.blocks.BinaryFlow` (If
        binary  object is present, CAUTION: replaces
        :py:class:`~oemof.solph.blocks.Flow` class)

    Examples
    --------
    Creating a fixed flow object:

    >>> f = Flow(actual_value=[10, 4, 4], fixed=True, variable_costs=5)
    >>> f.variable_costs[2]
    5
    >>> f.actual_value[2]
    4

    Creating a flow object with time-depended lower and upper bounds:

    >>> f1 = Flow(min=[0.2, 0.3], max=0.99, nominal_value=100)
    >>> f1.max[1]
    0.99

    """

    def __init__(self, **kwargs):
        # TODO: Check if we can inherit from pyomo.core.base.var _VarData
        # then we need to create the var object with
        # pyomo.core.base.IndexedVarWithDomain before any Flow is created.
        # E.g. create the variable in the energy system and populate with
        # information afterwards when creating objects.

        scalars = ['nominal_value', 'fixed_costs', 'summed_max', 'summed_min',
                   'investment', 'binary', 'discrete', 'fixed']
        sequences = ['actual_value', 'positive_gradient', 'negative_gradient',
                     'variable_costs', 'min', 'max']
        defaults = {'fixed': False, 'min': 0, 'max': 1}

        for attribute in set(scalars + sequences + list(kwargs)):
            value = kwargs.get(attribute, defaults.get(attribute))
            setattr(self, attribute,
                    sequence(value) if attribute in sequences else value)

        if self.fixed and self.actual_value is None:
            raise ValueError("Can not fix flow value to None. "
                             "Please set actual_value of the flow")

        elif self.fixed:
            # ToDo: Check if min/max are set by user than raise warning
            # warnings.warn(
            #     "Values for min/max will be ignored if fixed is True.",
            #     SyntaxWarning)
            self.min = sequence(0)
            self.max = sequence(1)
        if self.investment and self.nominal_value is not None:
            self.nominal_value = None
            warnings.warn(
                "Using the investment object the nominal_value" +
                " is set to None.",
                SyntaxWarning)
        if self.investment and self.binary:
            raise ValueError("Investment flows cannot be combined with " +
                             "binary flows!")


class Bus(on.Bus):
    """A balance object. Every node has to be connected to Bus.

    Notes
    -----
    The following sets, variables, constraints and objective parts are created
     * :py:class:`~oemof.solph.blocks.Bus`

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.balanced = kwargs.get('balanced', True)


class Sink(on.Sink):
    """An object with one input flow.
    """
    pass


class Source(on.Source):
    """An object with one output flow.
    """
    pass


class LinearTransformer(on.Transformer):
    """A Linear Transformer object.

    Parameters
    ----------
    conversion_factors : dict
        Dictionary containing conversion factors for conversion of inflow
        to specified outflow. Keys are output bus objects.
        The dictionary values can either be a scalar or a sequence with length
        of time horizon for simulation.

    Examples
    --------
    Defining an linear transformer:

    >>> bel = Bus()
    >>> bth = Bus()
    >>> bng = Bus()
    >>> trsf = LinearTransformer(conversion_factors={bel: 0.4,
    ...                                              bth: [1, 2, 3]},
    ...                          inputs={bng: Flow()})
    >>> trsf.conversion_factors[bel][3]
    0.4

    Notes
    -----
    The following sets, variables, constraints and objective parts are created
     * :py:class:`~oemof.solph.blocks.LinearTransformer`
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversion_factors = {
            k: sequence(v)
            for k, v in kwargs.get('conversion_factors', {}).items()}


class LinearN1Transformer(on.Transformer):
    """A Linear N:1 Transformer object.

    Parameters
    ----------

    conversion_factors : dict
        Dictionary containing conversion factors for conversion of inflow(s)
        to specified outflow. Keys are output bus objects.
        The dictionary values can either be a scalar or a sequence with length
        of time horizon for simulation.

    Examples
    --------
    Defining an linear transformer:

    >>> gas = Bus()
    >>> biomass = Bus()
    >>> trsf = LinearN1Transformer(conversion_factors={gas: 0.4,
    ...                                                biomass: [1, 2, 3]})
    >>> trsf.conversion_factors[gas][3]
    0.4

    Notes
    -----
    The following sets, variables, constraints and objective parts are created
     * :py:class:`~oemof.solph.blocks.LinearN1Transformer`
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversion_factors = {
            k: sequence(v)
            for k, v in kwargs.get('conversion_factors', {}).items()}
