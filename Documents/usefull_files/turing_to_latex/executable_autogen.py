#!/usr/bin/python

import os
import pydot

block_width_limit = 75;
block_ending_string = " \\\\ \n& ";
template_path = "turing_machine_template.tex";

def gen(source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student, uniquename):

    source_path = f"{uniquename}.txt";
    target_path = f"{uniquename}.tex";
    transition_diagram_path = f"transition_diagram_{uniquename}.png";

    if starting_state == "0":
        starting_state_description = "in this code it is also $ 0 $."
    else:
        starting_state_description = f"but in this code it is $ {starting_state} $, so it is necessary to set it before starting the machine."

    if not os.path.isfile(source_path):
        raise Exception(f"{source_path} not found");

    if not os.path.isfile(template_path):
        raise Exception(f"{template_path} not found");

    source = open(source_path, "r");

    tape_letters = {};
    for letter in tape_letters_raw:
        tape_letters[letter.replace("_", "\\_")] = None;

    source_letters = {};
    for letter in source_letters_raw:
        source_letters[letter.replace("_", "\\_")] = None;

    extra_letters = dict.fromkeys(tape_letters.keys());
    for source_letter in source_letters:
        extra_letters.pop(source_letter);

    sanitized_source = "";
    line_index = 0;
    for line in source:
        if line.startswith(";"):
            print(f"Skipped {line}");
        elif line == "\n":
            print("Skipped empty line");
        else:
            line = line.split(";")[0].strip();
            if len(line) == 0:
                print("Skipped empty line");
                continue;
            if line_index > 0:
                sanitized_source += "\n";
            sanitized_source += line;
            line_index = line_index + 1;
            print(f"accepted {line}");

    sanitized_source = sanitized_source.replace("_", "\\_");
    sanitized_source = sanitized_source.replace("#", "\\#");

    print(f"\nSanitized source: \n {sanitized_source}");

    state_map = {};
    states = {};

    # make a raw state map
    for rule in sanitized_source.split("\n"):
        # filter empty parts
        rule_split = rule.split(" ");
        rule_split[:] = [part for part in rule_split if part];

        states[rule_split[0]] = None;

        # normalize current and next symbol
        if rule_split[2] == "*" and rule_split[1] != "*":
            rule_split[2] = rule_split[1]

        state_map[rule_split[0] + " " + rule_split[1]] = rule_split[2] + " " + rule_split[3] + " " + rule_split[4];

    if accept_state != "":
        states[accept_state] = None;

    if reject_state != "":
        states[reject_state] = None;

    print(f"State map (stage 1): \n {state_map}");

    unwrapped_state_map = {};

    # expand all * symbols in the map
    for rule_key in state_map: # explicitly copy the keys because we will modify the map later
        rule_key_split = rule_key.split(" ");
        # 0 is current state, 1 is current symbol
        rule_value = state_map[rule_key];
        # expand * if possible
        if rule_key_split[1] == "*":
            print(f"Expanding {rule_key}");
            for letter in tape_letters:
                new_key = rule_key_split[0] + " " + letter;
                # we don't have an expilicitly defined fule for that state-symbol pair, add it
                if new_key not in state_map:
                    rule_value_split = rule_value.split(" ");
                    # 0 is new symbol, 1 is direction, 2 is new state
                    # * -> * symbol doesn't change
                    if rule_value_split[0] == "*":
                        rule_value_split[0] = letter;

                    print(f"Expanded {rule_key} to {new_key}")

                    unwrapped_state_map[new_key] = " ".join(rule_value_split);
                else:
                    print(f"Skipped expansion of {rule_key} to {new_key}, key already exists")
        else:
            unwrapped_state_map[rule_key] = rule_value;

    state_map = unwrapped_state_map;

    print(f"State map (stage 2): \n {state_map}");


    def appendToSet(set_string, string_to_append, current_length, current_index, max_len, separator = ", "):
        set_string += string_to_append;
        current_length += len(string_to_append);

        if current_index < max_len - 1:
            set_string += separator
            current_length += 2;

            if current_length > block_width_limit:
                set_string += block_ending_string;
                current_length = 0;

        return current_length, set_string


    domain_of_definition = "& ";
    domain_of_definition_last_len = 0;

    transition_range = "& ";
    transition_range_last_len = 0;

    transition_function = "& ";
    transition_function_last_len = 0;

    formatted_state_map = {};
    value_length_per_letter = {};

    for tape_letter in tape_letters:
        value_length_per_letter[tape_letter] = 6

    print("\n Unwrapped turing machine: \n");
    index = 0;
    for rule_key in state_map:
        rule_value = state_map[rule_key];

        key = f"({rule_key.replace(' ', ', ')})";
        value = f"({rule_value.replace(' ', ', ')})";

        key_letter = rule_key.split(" ")[1];
        # store maximum length for each letter, will be used for formatting later
        value_length_per_letter[key_letter] = max(value_length_per_letter.get(key_letter, 0), len(value));

        # store formatted value for future use
        formatted_state_map[rule_key] = value;

        domain_of_definition_last_len, domain_of_definition = appendToSet(domain_of_definition,
                                                                        key,
                                                                        domain_of_definition_last_len,
                                                                        index,
                                                                        len(state_map));

        transition_range_last_len,     transition_range =     appendToSet(transition_range,
                                                                        value,
                                                                        transition_range_last_len,
                                                                        index,
                                                                        len(state_map));

        transition_function_last_len,  transition_function =  appendToSet(transition_function,
                                                                        f"({key}, {value})",
                                                                        transition_function_last_len,
                                                                        index,
                                                                        len(state_map));

        print(f"{rule_key} {rule_value}");
        index += 1;


    state_str = "& "
    state_str_last_len = 0;
    index = 0;

    for state in states:
        state_str_last_len, state_str = appendToSet(state_str,
                                                        state,
                                                        state_str_last_len,
                                                        index,
                                                        len(states),
                                                        separator = ", \\; ");
        index += 1;


    print(f"\n Input letters: \n{source_letters}\n");
    print(f"\n Tape letters: \n{tape_letters}\n");
    print(f"\n Extra tape letters: \n{extra_letters}\n");
    print(f"\n States: \n{state_str}\n");
    print(f"\n Domain of definition: \n{domain_of_definition}\n");
    print(f"\n Transition range: \n{transition_range}\n");
    print(f"\n Transition function: \n{transition_function}\n");

    state_symbol_cartesian = "& ";
    state_symbol_cartesian_last_len = 0;

    state_symbol_direction_cartesian = "& ";
    state_symbol_direction_cartesian_last_len = 0;

    index = 0;
    for state in states:
        for letter in tape_letters:

            state_symbol_cartesian_last_len, state_symbol_cartesian = appendToSet(state_symbol_cartesian,
                                                                                f"({state}, {letter})",
                                                                                state_symbol_cartesian_last_len,
                                                                                index,
                                                                                len(states) * len(tape_letters));

            state_symbol_direction_cartesian_last_len, state_symbol_direction_cartesian = appendToSet(state_symbol_direction_cartesian,
                                                                                                    f"({state}, {letter}, L), ({state}, {letter}, R)",
                                                                                                    state_symbol_direction_cartesian_last_len,
                                                                                                    index,
                                                                                                    len(states) * len(tape_letters));

            index += 1;

    print(f"\n QxG: \n{state_symbol_cartesian}\n");
    print(f"\n QxGx(L, R): \n{state_symbol_direction_cartesian}\n");

    state_symbol_cartesian_cardinality = len(states) * len(tape_letters);
    state_symbol_direction_cartesian_cardinality = state_symbol_cartesian_cardinality * 2;

    print(f"\n Cardinality of QxG: {state_symbol_cartesian_cardinality}\n");
    print(f"\n Cardinality of QxGx(L, R): {state_symbol_direction_cartesian_cardinality}\n");

    # find longest state width to print with constant width
    longest_state = len("Q $ states");
    for state in states:
        longest_state = max(longest_state, len(state));

    # write out header
    transition_table = f"$ {'Q $ states   ':<{longest_state}}";
    for letter in tape_letters:
        transition_table += f"& ~~~~{letter:<{value_length_per_letter[letter] - 1}}"
    transition_table += "\\\\ \\midrule\n"

    # main body
    for state in states:
        transition_table += f"$ {state:<{longest_state}} $ "
        for letter in tape_letters:
            transition_table += f"& ${formatted_state_map.get(state + ' ' + letter, ' '):<{value_length_per_letter[letter]}}$ ";
        transition_table += "\\\\ \n"

    print(f"\n Transition table: \n{transition_table}\n");


    graph = pydot.Dot("transition_diagram", graph_type="digraph", bgcolor="white", center="true")

    for state in states:
        graph.add_node(pydot.Node(state, label=state, shape="circle"));

    # map of state -> state : label
    graph_map = {}

    for state_key in state_map:
        state_value = state_map[state_key];

        state_key_split = state_key.split(" "); # 0 is current state, 1 is current symbol
        state_value_split = state_value.split(" "); # 0 is new symbol, 1 is direction, 2 is new state

        transition_key = state_key_split[0] + " " + state_value_split[2];
        transition_label = f"{state_key_split[1]} → {state_value_split[0]}, {state_value_split[1]}";

        if transition_key not in graph_map:
            graph_map[transition_key] = transition_label;
        else:
            graph_map[transition_key] += "\n" + transition_label;

    for node in graph_map:

        node_split = node.split(" "); # 0 is current state, 1 is next state
        label = graph_map[node];

        graph.add_edge(pydot.Edge(node_split[0], node_split[1], color="black", fontcolor="blue", arrowhead="normal", label = label))

    graph.write_png(transition_diagram_path);

    f = open(template_path, "r");
    f_target = open(target_path, "w");

    template = f.read();

    source.seek(0);
    template = template.replace("%%CODE_LISTING%%", source.read());
    template = template.replace("%%STUDENT%%", student);
    template = template.replace("%%STATES%%", state_str);
    template = template.replace("%%STARTING_STATE%%", starting_state);
    template = template.replace("%%STARTING_STATE_DESCRIPTION%%", starting_state_description);

    template = template.replace("%%ACCEPT_STATE%%", accept_state);

    if reject_state == "":
        template = template.replace("%%REJECT_STATE_NULL_MESSAGE%%", "");

    template = template.replace("%%REJECT_STATE%%", "\\lambda" if reject_state == "" else reject_state);

    template = template.replace("%%SOURCE_LETTERS%%", ", ".join(source_letters));
    template = template.replace("%%EXTRA_LETTERS%%", ", ".join(extra_letters));
    template = template.replace("%%NUM_TAPE_LETTERS%%", str(len(tape_letters)));
    template = template.replace("%%NUM_STATES%%", str(len(states)));
    template = template.replace("%%QG_CARDINALITY%%", str(state_symbol_cartesian_cardinality));
    template = template.replace("%%QGLR_CARDINALITY%%", str(state_symbol_direction_cartesian_cardinality));

    template = template.replace("%%DOMAIN_OF_DEFINITION%%", domain_of_definition);
    template = template.replace("%%TRANSITION_RANGE%%", transition_range);
    template = template.replace("%%TRANSITION_FUNCTION%%", transition_function);

    first_key = next(iter(state_map));
    template = template.replace("%%FIRST_KEY%%", f"({first_key.replace(' ', ', ')})");
    template = template.replace("%%FIRST_VALUE%%", formatted_state_map[first_key]);

    template = template.replace("%%CARTESIAN_QG%%", state_symbol_cartesian);
    template = template.replace("%%CARTESIAN_QGLR%%", state_symbol_direction_cartesian);

    template = template.replace("%%TRANSITION_TABLE%%", transition_table);

    template = template.replace("%%TRANSITION_DIAGRAM%%", transition_diagram_path);

    f_target.write(template);

    f.close();
    source.close();
    f_target.close();

    print("DONE");

    return target_path, transition_diagram_path;

if __name__ == "__main__":
    gen(source_letters_raw=dict.fromkeys(["a", "b", "c"]),
        tape_letters_raw=dict.fromkeys(["a", "b", "c", "_"]),
        accept_state="halt-accept",
        reject_state="",
        starting_state="0",
        student="Danila Gudim",
        uniquename="turing")
