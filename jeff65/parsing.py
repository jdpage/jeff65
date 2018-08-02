# jeff65 parser generator
# Copyright (C) 2018  jeff65 maintainers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import attr
import re
import time


class ParseError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@attr.s(slots=True, frozen=True)
class TextSpan:
    start_line = attr.ib()
    start_column = attr.ib()
    end_line = attr.ib()
    end_column = attr.ib()

    def __attrs_post_init__(self):
        if self.start > self.end:
            t = self.start_line
            object.__setattr__(self, 'start_line', self.end_line)
            object.__setattr__(self, 'end_line', t)
            t = self.start_column
            object.__setattr__(self, 'start_column', self.end_column)
            object.__setattr__(self, 'end_column', t)

    @property
    def start(self):
        return (self.start_line, self.start_column)

    @property
    def end(self):
        return (self.end_line, self.end_column)

    def __bool__(self):
        return self.start < self.end

    def __contains__(self, other):
        return (
            isinstance(other, TextSpan)
            and self.start <= other.start
            and other.end <= self.end)

    @staticmethod
    def cover(spans):
        """Return a TextSpan covering all of the given spans.

        The result is the shortest span t such that every given is contained in
        it. Note that because TextSpans are always contiguous, there may exist
        spans which are not contained in any of the given spans, but are
        contained in the cover span.
        """
        return TextSpan(
            *min(s.start for s in spans),
            *max(s.end for s in spans))

    def __str__(self):
        start = f'{self.start_line}:{self.start_column}'
        end = f'{self.end_line}:{self.end_column}'
        return f'{start}-{end}'


@attr.s(slots=True, frozen=True)
class Token:
    t = attr.ib()
    text = attr.ib()
    channel = attr.ib(default=0, cmp=False)
    span = attr.ib(default=None, cmp=False)

    def _pretty(self, indent):
        yield (indent, f'{self.t}={self.text!r} {self.span}')


class ReStream:
    """Regex-matchable stream."""

    CHANNEL_ALL = -1
    CHANNEL_DEFAULT = 0
    CHANNEL_HIDDEN = 1

    def __init__(self, stream):
        self.stream = iter(stream)
        self.current = None
        self.line = 0
        self.column = 0

        try:
            self.advance_line()
        except StopIteration:
            self.current = ""
            self.line = 1

    def advance_line(self):
        """Advance the stream position to the beginning of the next line."""
        try:
            self.current = next(self.stream)
        except StopIteration:
            raise
        else:
            self.line += 1
            self.column = 0

    def assure_line(self):
        """Assures that at least one character remains in the current line."""
        if self.column == len(self.current):
            self.advance_line()

    def match(self, regex):
        """Match the given regex at the current stream position.

        In order to actually advance the position, call ReStream.produce() with
        the returned match object.

        Returns a match object if successful, None otherwise.
        """

        self.assure_line()
        return regex.match(self.current, self.column)

    def produce(self, symbol, match, channel=CHANNEL_DEFAULT):
        """Produce a token and advance the position."""

        token = Token(symbol, match.group(), channel,
                      TextSpan(
                          self.line, self.column,
                          self.line, match.end()))
        self.column = match.end()
        return token

    def rewind(self, token: Token):
        """Rewinds by one token.

        This may only be called if the last method to be called on the ReStream
        object was the produce() call which returned the given token.
        """

        assert token.span.end == (self.line, self.column)
        self.column = token.span.start_column

    def produce_eof(self, symbol):
        """Produce an EOF token."""
        return Token(symbol, None, self.CHANNEL_ALL,
                     TextSpan(self.line, self.column, self.line, self.column))


class Lexer:
    def __init__(self, eof, rules):
        """Create a lexer callable.

        rules should be a list of tuples of one of the following forms:
          (pattern, token_type)
          (mode, pattern, token_type)
          (mode, pattern, token_type, channel)
        """

        self.eof = eof
        self.mode_rules = {}
        for mptc in rules:
            mode, channel = Parser.NORMAL_MODE, ReStream.CHANNEL_DEFAULT
            if len(mptc) == 2:
                pattern, tt = mptc
            elif len(mptc) == 3:
                mode, pattern, tt = mptc
            else:
                mode, pattern, tt, channel = mptc
            rs = self.mode_rules.setdefault(mode, [])
            rs.append((re.compile(pattern), tt, channel))

    def __call__(self, stream: ReStream, mode: int) -> Token:
        try:
            stream.assure_line()
        except StopIteration:
            return stream.produce_eof(self.eof)

        for regex, tt, channel in self.mode_rules[mode]:
            m = stream.match(regex)
            if m:
                return stream.produce(tt, m, channel)
        assert False, "no match!"  # TODO: proper exception


@attr.s(slots=True, frozen=True, repr=False)
class Rule:
    lhs = attr.ib()
    rhs = attr.ib(converter=tuple)
    prec = attr.ib(default=None)
    rassoc = attr.ib(default=False)
    mode = attr.ib(default=0)  # Parser.NORMAL_MODE
    pointer = attr.ib(default=None)

    def with_pointer(self, pointer):
        return attr.evolve(self, pointer=pointer)

    @property
    def next_symbol(self):
        if self.pointer is None:
            raise Exception('Rule has no pointer')
        elif self.pointer == len(self.rhs):
            return None
        return self.rhs[self.pointer]

    @property
    def advanced(self):
        if self.pointer is None:
            raise Exception('Rule has no pointer')
        elif self.pointer == len(self.rhs):
            raise Exception('Rule cannot be advanced')
        return self.with_pointer(self.pointer + 1)

    @property
    def parent(self):
        """Gets the parent rule if this is an extended rule."""
        return attr.evolve(self, lhs=self.lhs[1], rhs=[s[1] for s in self.rhs])

    def __repr__(self):
        toks = list(self.rhs)
        if self.pointer is not None:
            toks.insert(self.pointer, '.')
        rhs = ' '.join(str(t) for t in toks)
        if self.prec is not None:
            return f'{self.lhs} -> {rhs} ({self.prec})'
        return f'{self.lhs} -> {rhs}'


class ItemSet:
    def __init__(self, grammar, items):
        self.items = set(items)

        # complete the itemset by repeatedly finding all of the productions
        # which come after pointers in the set, and adding all the rules that
        # produce them recursively.
        while True:
            old_size = len(self.items)
            nexts = {r.next_symbol for r in self.items
                     if r.next_symbol is not None
                     and not grammar.is_terminal(r.next_symbol)}
            self.items.update(
                grammar.rules[r].with_pointer(0)
                for r in grammar.find_rule_indices(nexts))
            if len(self.items) == old_size:
                break

    @property
    def next_symbols(self):
        """Gets a list of possible next symbols."""
        return {r.next_symbol for r in self.items
                if r.next_symbol is not None}

    def advance(self, symbol):
        """Advances the itemset by the given symbol.

        Returns a frozenset of items where items which can be advanced by the
        given symbol have been, and items which cannot have been dropped.
        """
        return frozenset(
            item.advanced for item in self.items if item.next_symbol == symbol)


class Grammar:
    EMPTY = object()
    END = object()

    def __init__(self, start_symbol, end_symbols, rules):
        self.rules = rules
        self.start_symbol = start_symbol
        self.end_symbols = end_symbols

    @property
    def symbols(self):
        ts = set()
        for rule in self.rules:
            ts.add(rule.lhs)
            ts.update(rule.rhs)
        return ts

    def is_terminal(self, t):
        if isinstance(t, str):
            # we represent bare nonterminals as strings
            return False

        try:
            # try to unpack as a tuple (in case it's an extended symbol)
            _, t, _ = t
        except TypeError:
            # must be a terminal
            return True

        # try again now that it's unpacked
        return self.is_terminal(t)

    def find_rule_indices(self, symbols):
        """Returns a list of rule indices which produce the given symbols."""
        return [k for k, r in enumerate(self.rules) if r.lhs in symbols]

    def find_starting_rule_index(self):
        """Finds the starting rule given the start symbol."""
        starts = self.find_rule_indices([self.start_symbol])
        if len(starts) == 0:
            raise Exception('No starting rule found')
        elif len(starts) > 1:
            raise Exception('Multiple starting rules found')
        elif len(self.rules[starts[0]].rhs) != 1:
            raise Exception('Starting rule must have one token')
        else:
            return starts[0]

    def find_rules(self, symbols):
        """Returns a list of rules which produce the given symbols."""
        return [r for r in self.rules if r.lhs in symbols]

    def build_firstsets(self):
        """Builds the First sets for every extended symbol.

        The First set is the set of all terminals which can grammatically
        appear at the beginning of a given symbol.
        """

        start_time = time.perf_counter()
        firstsets = {}

        # pre-populate with empty firstsets (for nonterminals) and identity
        # firstsets (for terminals)
        for sym in self.symbols:
            if self.is_terminal(sym):
                try:
                    firstsets[sym] = {sym[1]}
                except TypeError:
                    firstsets[sym] = {sym}
            else:
                firstsets[sym] = set()

        # 1. if V -> x, then First(V) contains x
        # 2. if V -> (), then First(V) contains ()
        nzrules = []
        for rule in self.rules:
            if len(rule.rhs) == 0:
                firstsets[rule.lhs].add(self.EMPTY)
            elif self.is_terminal(rule.rhs[0]):
                firstsets[rule.lhs].update(firstsets[rule.rhs[0]])
            else:
                # cache rules that rule 3 applies to in advance
                nzrules.append(rule)

        # 3. if V -> A B C, then First(V) contains First(A) - (). If First(A)
        #    contains (), then First(V) also contains First(B), etc. If A, B,
        #    and C all contain (), then First(V) contains ().
        #
        # Since rules can be (mutually) left-recursive, we may have to apply
        # this rule multiple times to catch everything.
        updated = True
        count = 0
        while updated:
            count += 1
            updated = False
            for rule in nzrules:
                # we know in advance that these rules begin with a nonterminal
                # on the right-hand side, because they're the ones we cached
                # when applied rules 1 & 2.
                old_len = len(firstsets[rule.lhs])
                for symbol in rule.rhs:
                    if self.EMPTY not in firstsets[symbol]:
                        firstsets[rule.lhs].update(firstsets[symbol])
                        break
                    firstsets[rule.lhs].update(
                        firstsets[symbol] - {self.EMPTY})
                else:
                    firstsets[rule.lhs].add(self.EMPTY)
                if len(firstsets[rule.lhs]) > old_len:
                    updated = True

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        print(f'Built firstsets ({count} cycles) in {elapsed_ms:.2f}ms')
        return firstsets

    def build_followsets(self):
        """Builds the Follow sets for every extended symbol.

        The Follow set is the set of all terminals which can grammatically
        appear after the given symbol.
        """

        firstsets = self.build_firstsets()
        start_time = time.perf_counter()
        followsets = {}

        # pre-populate with empty followsets
        for sym in self.symbols:
            if sym == self.start_symbol:
                try:
                    followsets[sym] = {s[1] for s in self.end_symbols}
                except TypeError:
                    followsets[sym] = set(self.end_symbols)
            else:
                followsets[sym] = set()

        # suppose we have a rule R -> a*Db. Then we add First(b) to Follow(D).
        for rule in self.rules:
            for k in range(len(rule.rhs) - 1):
                if not self.is_terminal(rule.rhs[k]):
                    followsets[rule.rhs[k]].update(
                        firstsets[rule.rhs[k+1]])

        # suppose we have a rule R -> a*D. Then we add Follow(R) to Follow(D).
        # Because we can end up with irritating things like two follow sets
        # mutually depending on each other, we've handled this by just applying
        # the rule until we reach a fixed state.
        updated = True
        count = 0
        while updated:
            count += 1
            updated = False
            for rule in self.rules:

                # empty rules don't tell us anything for this pass
                if len(rule.rhs) == 0:
                    continue

                if not self.is_terminal(rule.rhs[-1][1]):
                    old_len = len(followsets[rule.rhs[-1]])
                    followsets[rule.rhs[-1]].update(
                        followsets[rule.lhs])
                    if len(followsets[rule.rhs[-1]]) > old_len:
                        updated = True

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        print(f'Built followsets ({count} cycles) in {elapsed_ms:.2f}ms')
        return followsets

    def build_parser(self, hidden=None, channel=ReStream.CHANNEL_DEFAULT):
        print(f'Grammar has {len(self.rules)} rules')

        start_time_t = time.perf_counter()
        translation_table = TranslationTable(self)
        extended_grammar = translation_table.build_extended_grammar()
        modes = translation_table.build_modes()
        followsets = extended_grammar.build_followsets()
        start_time = time.perf_counter()

        # Build the action/goto table. This is what the parse function actually
        # uses. In the action part of the table (where the input is a
        # terminal), there are two possible actions: shift, and reduce. These
        # are represented by an (action, index) tuple. In response to a reduce,
        # the parser will execute a goto by providing a nonterminal as input.
        # These are represented as integers.
        agtable = {}

        # copy the nonterminal entries in the translation table over as gotos
        # and the terminal entries as shifts.
        for (f, s), t in translation_table.items():
            if self.is_terminal(s):
                agtable[(f, s)] = ('shift', None, t)
            else:
                agtable[(f, s)] = t  # goto

        # construct the final sets by merging extended rules which are based on
        # the same rule and have the same end point.
        finalset_rules = [None] * len(translation_table.itemsets)
        finalset_followsets = [set() for _ in translation_table.itemsets]
        for rule in extended_grammar.rules:
            if len(rule.rhs) == 0:
                # if the rule has no rhs, then the starting point is the same
                # as the ending point.
                final = rule.lhs[0]
            else:
                final = rule.rhs[-1][2]
            if finalset_rules[final] is not None:
                assert finalset_rules[final] == rule.parent, (
                    f'reduce/reduce:\n' +
                    f'  {finalset_rules[final]}\n' +
                    f'  {rule.parent}')
            finalset_rules[final] = rule.parent
            finalset_followsets[final].update(followsets[rule.lhs])

        # add the merged reductions to the table
        for k, followset in enumerate(finalset_followsets):
            for symbol in followset:
                if (k, symbol) in agtable:
                    # This is a shift/reduce conflict. We decide how to resolve
                    # this based on the precedence of the rules involved.

                    # Note that the shift index is a state number, not a rule
                    # number. State numbers correspond to item sets. In
                    # particular, we're looking for the rule that has already
                    # been partially applied.
                    _, _, shift_index = agtable[(k, symbol)]
                    partials = [
                        i for i
                        in translation_table.itemsets[shift_index].items
                        if i.pointer > 0]
                    assert len(partials) == 1, 'shift/reduce (GENERATOR BUG)'
                    shift_rule = partials[0]

                    # If one of them is missing a precedence, go ahead and
                    # hard-fail.
                    assert shift_rule.prec is not None \
                        and finalset_rules[k].prec is not None, \
                        f'shift/reduce:\n  {shift_rule}\n  {finalset_rules[k]}'

                    # If the shifting rule is right-associative, then we should
                    # break ties in favour of the shift. Otherwise, in favour
                    # of the reduce. Note because we look at the shift rule's
                    # associativity for this decision, a right-associative rule
                    # will bind more tightly than a left-associative rule with
                    # the same precedence.
                    if (shift_rule.prec > finalset_rules[k].prec
                        or (shift_rule.rassoc
                            and shift_rule.prec == finalset_rules[k].prec)):
                        continue

                # Check to see if this is actually the accept state
                if finalset_rules[k].lhs == self.start_symbol \
                   and symbol in self.end_symbols:
                    agtable[(k, symbol)] = ('accept', None, None)
                else:
                    agtable[(k, symbol)] = (
                        'reduce',
                        finalset_rules[k].lhs,
                        len(finalset_rules[k].rhs))

        # build the hidden-channel parsers
        hidden_parsers = {
            channel: aux_grammar.build_parser(channel=channel)
            for channel, aux_grammar in (hidden or {}).items()
        }

        parser = Parser(agtable, modes, hidden_parsers, channel)
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        elapsed_t_ms = (end_time - start_time_t) * 1000
        print(f'Built action/goto table ({len(agtable)} entries)',
              f'in {elapsed_ms:.2f}ms')
        print(f'Built parser in {elapsed_t_ms:.2f}ms total')
        print(f'Symbols: {len(self.symbols)},',
              f'States: {len(translation_table.itemsets)}')
        return parser


class TranslationTable:
    """A table of itemset/state transitions."""

    def __init__(self, grammar):
        self.end_symbols = grammar.end_symbols
        self.translation_table = {}
        self.itemsets = []
        self.itemset_index = {}

        start_time = time.perf_counter()

        # The first item set is based around the start rule
        start = grammar.find_starting_rule_index()
        startitem = grammar.rules[start].with_pointer(0)
        self.itemsets.append(ItemSet(grammar, {startitem}))
        self.itemset_index[frozenset({startitem})] = 0

        # next, we work our way down the itemsets, advancing them using the
        # allowed productions. The resulting items are used to construct new
        # itemsets. We also build the translation table as we go
        current = 0
        while current < len(self.itemsets):
            for symbol in self.itemsets[current].next_symbols:
                key = self.itemsets[current].advance(symbol)
                if key in self.itemset_index:
                    itemset = self.itemset_index[key]
                else:
                    itemset = len(self.itemsets)
                    self.itemset_index[key] = itemset
                    self.itemsets.append(ItemSet(grammar, key))
                self.translation_table[(current, symbol)] = itemset
            current += 1

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        print(f'Built {current} itemsets in {elapsed_ms:.2f}ms')

    def items(self):
        return self.translation_table.items()

    def build_extended_grammar(self):
        """Builds the extended rule set.

        This produces a set of rules where each symbol sym has been replaced
        with the triple (s0, sym, s1) where s0 is the state/itemset preceding
        that symbol, and s1 is the state/itemset following it. If the rule can
        be applied from multiple states (i.e. it shows up in multiple
        itemsets), it will show up multiple times with different state numbers.
        """
        start_time = time.perf_counter()
        extended_rules = set()

        for current, itemset in enumerate(self.itemsets):
            for rule in itemset.items:
                if rule.pointer != 0:
                    continue
                prev = None
                state = current
                rhs = []
                for symbol in rule.rhs:
                    prev = state
                    state = self.translation_table[(state, symbol)]
                    rhs.append((prev, symbol, state))
                try:
                    lhs = (current, rule.lhs,
                           self.translation_table[(current, rule.lhs)])
                except KeyError:
                    lhs = (current, rule.lhs, Grammar.END)
                    start_symbol = lhs
                extended_rules.add(
                    attr.evolve(rule, lhs=lhs, rhs=rhs, pointer=None))

        extended_grammar = Grammar(
            start_symbol,
            [(None, s, None) for s in self.end_symbols],
            extended_rules)
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        sz = len(extended_rules)
        print(f'Built extended grammar ({sz} rules) in {elapsed_ms:.2f}ms')
        return extended_grammar

    def build_modes(self):
        """Builds the lexer mode table.

        Depending on what rule we are currently following, we ask the lexer to
        operate in different modes. Each itemset/state is associated with one
        mode, that of the rule(s) which are currently in-progress.
        """
        modes = []

        for itemset in self.itemsets:
            partials = [r for r in itemset.items if r.pointer > 0]
            ms = {r.mode for r in partials}
            if len(ms) == 0:
                modes.append(Parser.NORMAL_MODE)
            else:
                assert len(ms) == 1, f"mode/mode conflict: {partials}"
                modes.append(ms.pop())

        return modes


class Parser:
    NORMAL_MODE = 0

    def __init__(self, agtable, modes, hidden, channel):
        self.agtable = agtable
        self.modes = modes
        self.hidden = hidden
        self.channel = channel

    def next_token_skip_hidden(self, stream, next_token, state):
        while True:
            lookahead = next_token(stream, self.modes[state])
            if lookahead.channel == self.channel \
               or lookahead.channel == ReStream.CHANNEL_ALL:
                return lookahead

            # When a token comes in on a channel other than the one we're
            # handling, we delegate to another parser for that channel, which
            # consumes the input. This is useful for things like comments,
            # which can show up anywhere -- handling them in the main grammar
            # would be impossible.
            stream.rewind(lookahead)
            p = self.hidden[lookahead.channel]
            p(stream, next_token, lambda t, s, c, m: None)

    def __call__(self, stream, next_token, make_node):
        """Parses a given input.

        This method may be called multiple times and does not modify the
        object.

        'next_token' must be a callable which takes two arguments: the
        'stream', and an int for the mode, which is 0 initially. It must return
        a Token.

        'make_node' must be a callable, which is called every time a reduction
        is performed. It is passed three arguments: the nonterminal being
        reduced, a span covering the tokens involved in the reduction, and an
        iterable of the children of the reduction, which are a mix of Tokens
        and values returned from make_node.
        """

        # start_time = time.perf_counter()
        output = []
        set_stack = [0]
        lookahead = self.next_token_skip_hidden(
            stream, next_token, set_stack[-1])

        while True:
            try:
                action, sym, arg = self.agtable[(set_stack[-1], lookahead.t)]
            except KeyError:
                msg = [f"Got {lookahead} but expected one of:"]
                for state, token in self.agtable:
                    if state == set_stack[-1]:
                        msg.append(f"  {token}")
                raise ParseError("\n".join(msg))

            if action == 'accept':
                break
            elif action == 'shift':
                output.append((lookahead, lookahead.span))
                set_stack.append(arg)
                lookahead = self.next_token_skip_hidden(
                    stream, next_token, set_stack[-1])
            elif action == 'reduce':
                if arg > 0:
                    children, spans = zip(*output[-arg:])
                    span = TextSpan.cover(spans)
                    del output[-arg:]
                    del set_stack[-arg:]
                else:
                    children = []
                    # Since we are reducing an empty rule, we know by [vigorous
                    # handwaving] that the lack-of-tokens we're trying to
                    # reduce is bounded on the left by the last item in the
                    # output stack (if present) and on the right by the
                    # lookahead token. Note that this approach may result in
                    # the span corresponding to a block of whitespace or a
                    # comment.
                    end = lookahead.span.start
                    if len(output) > 0:
                        start = output[-1][1].end
                    else:
                        start = end
                    span = TextSpan(*start, *end)
                set_stack.append(self.agtable[(set_stack[-1], sym)])
                output.append((make_node(sym, span, children,
                                         self.modes[set_stack[-1]]),
                               span))

        assert len(output) == 1

        # end_time = time.perf_counter()
        # elapsed_ms = (end_time - start_time) * 1000
        # TODO: log to debug log
        # print(f'Parsed input in {elapsed_ms:.2f}ms')
        return output[0][0]
