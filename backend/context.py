import copy
from type_objects import NoneType, Bool
from util import type_intersection, UnknownValue

# Tricky: need to support obj1.obj2.x where obj2 is an instance
# of a class that may not be defined in the current scope
# Idea: maintain a separate scope dict that contains all the class
# type data, keyed by classname
# Assume that all attributes are either set in __init__ or method names

# Also, if we import one function from another module, and that function
# calls another function that was not imported, we need to know the type
# of the other function without having it in our scope. Perhaps we should
# maintain two scopes. One for everything that is loaded, another for
# everything that is in scope. LoadScope vs. NameScope
# Whenever you add to LoadScope, it automatically adds to NameScope,
# but not the other way around.


def builtin_scope():
    scope = Scope()
    scope.add(Symbol('None', NoneType(), None))
    scope.add(Symbol('True', Bool(), True))
    scope.add(Symbol('False', Bool(), False))
    return scope


class Symbol(object):
    def __init__(self, name, type_=None, value=UnknownValue(),
                 assign_expression=None):
        assert name is not None
        assert type_ is not None
        self._name = None
        self._type = None
        self._value = None
        self._assign_expression = None
        self.assign(name, type_, value, assign_expression)

    def assign(self, name, type_, value, assign_expression):
        self._name = name
        self._type = type_
        self._value = value if type_ != NoneType() else None
        self._assign_expression = assign_expression

    def get_name(self):
        return self._name

    def get_type(self):
        return self._type

    def get_value(self):
        return self._value

    def __str__(self):
        if isinstance(self._value, UnknownValue):
            return str(self._type)
        return '{0} {1}'.format(self._type, self._value)


class Scope(object):
    def __init__(self, init_dict=None):
        self._symbols = {}
        self._return = None
        if init_dict is not None:
            for name, type_ in init_dict.iteritems():
                self.add(Symbol(name, type_, UnknownValue()))

    def __hash__(self):
        return hash(frozenset(self._symbols.items())) + hash(self._return)

    def names(self):
        return self._symbols.keys()

    def symbols(self):
        return copy.copy(self._symbols)

    def get(self, name):
        return self._symbols.get(name)

    def get_type(self, name=None):
        symbol = self.get(name) if name else self.get_return()
        return symbol.get_type() if symbol else None

    def get_value(self, name=None):
        symbol = self.get(name) if name else self.get_return()
        return symbol.get_value() if symbol else None

    def add(self, symbol):
        assert isinstance(symbol, Symbol)
        self._symbols[symbol.get_name()] = symbol

    def remove(self, name):
        del self._symbols[name]

    def merge(self, scope):
        assert isinstance(scope, Scope)
        self._symbols.update(scope.symbols())

    def set_return(self, symbol):
        assert isinstance(symbol, Symbol)
        self._return = symbol

    def get_return(self):
        return self._return

    def __str__(self):
        end = '\n' if len(self._symbols) > 0 else ''
        return '\n'.join(['{0} {1}'.format(name, self._symbols[name])
                          for name in sorted(self._symbols.keys())]) + end

    def __contains__(self, name):
        return name in self._symbols


class Context(object):
    def __init__(self, layers=None):
        self._scope_layers = [builtin_scope()] if layers is None else layers
        self._constraints = {}

    def __str__(self):
        return '\n'.join([str(layer) for layer in self._scope_layers])

    def __contains__(self, name):
        return any(name in scope for scope in self._scope_layers)

    def copy(self):
        """This makes a copy that won't lose scope layers when the original
        ends scopes, but it will still share the data structure for each
        scope."""
        return Context([scope for scope in self._scope_layers])

    def begin_scope(self, scope=None):
        self._scope_layers.append(Scope() if scope is None else scope)

    def end_scope(self):
        if len(self._scope_layers) <= 1:
            raise RuntimeError('Cannot close bottom scope layer')
        return self._scope_layers.pop()

    def get_top_scope(self):
        return self._scope_layers[-1]

    def add(self, symbol):
        assert isinstance(symbol, Symbol)
        self.get_top_scope().add(symbol)

    def remove(self, name):
        scope = self.find_scope(name)
        if scope is not None:
            scope.remove(name)

    def get(self, name):
        scope = self.find_scope(name)
        return scope.get(name) if scope is not None else None

    def get_type(self, name=None):
        symbol = self.get(name) if name else self.get_return()
        return symbol.get_type() if symbol else None

    def set_return(self, symbol):
        self.get_top_scope().set_return(symbol)

    def get_return(self):
        return self.get_top_scope().get_return()

    def merge_scope(self, scope):
        self.get_top_scope().merge(scope)

    def find_scope(self, name):
        for scope in reversed(self._scope_layers):
            if name in scope:
                return scope
        return None

    def add_constraint(self, name, type_):
        old_type = self._constraints.get(name, self.get_type(name))
        self._constraints[name] = (type_intersection(old_type, type_)
                                   if old_type is not None else type_)

    def get_constraints(self):
        return self._constraints

    def clear_constraints(self):
        self._constraints = {}


class ExtendedContext(Context):
    """ This class gives you a context that you can use and modify normally,
        but which extends a base context that you cannot modify. """
    def __init__(self, base_context):
        self._base_context = base_context
        super(ExtendedContext, self).__init__([Scope()])


    def add_constraint(self, name, type_):
        self._base_context.add_constraint(name, type_)

    def clear_constraints(self):
        self._base_context.clear_constraints()

    def get_constraints(self):
        return self._base_context.get_constraints()

    def __contains__(self, name):
        return (super(ExtendedContext, self).__contains__(name)
                or (name in self._base_context))

    def copy(self):
        raise RuntimeError('copy is not allowed on ' + self.__class__.__name__)

    def get(self, name):
        extended = super(ExtendedContext, self).get(name)
        if extended is not None:
            return extended
        else:
            return self._base_context.get(name)

    def __str__(self):
        extended = super(ExtendedContext, self).__str__()
        return str(self._base_context) + '\n' + extended
