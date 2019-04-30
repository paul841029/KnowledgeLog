import copy
from tree import rule_selector
from node import RuleNode
from pyDatalog import pyDatalog
from request import pull_from_fuseki
import loguru
import collections
import pprint


def extract_tuple_from_fuseki_response(response):
    for instance in response['results']['bindings']:
        yield instance['subject']['value'], instance['object']['value']

import re

QUERY_PRED = re.compile(r'(.*)\(.*\)')

def eval_datalog(data, rule):
    """
    Evaluation using pyDatalog.
    :param data: a list of tuple string
    :param rule: a string of tuple
    :return: a list of resulting tuple string
    """
    assert isinstance(data, list)
    assert isinstance(rule, str)


    def extract_query_predicate(rule):
        return QUERY_PRED.match(rule).group(1)

    def db2str(tuples):
        return "\n".join(["+%s(%s,%s)" % (s, p, o) for (s, p, o) in tuples])


    def result2tuplestring(result):
        query_pred = extract_tuple_from_fuseki_response(rule)
        for (s, o) in result:
            yield (s, query_pred, o)

    pyDatalog.clear()
    pyDatalog.load(db2str(data) + '\n' + rule)
    pyDatalog.create_terms()
    result = pyDatalog.ask(rule)

    return list(result2tuplestring(result))


def eval_prob_query(rules, input_db):
    """
    Evaluate datalog programs given rules and EDB
    :param rules:
    :param input_db:
    :return: A resulting output database
    """

    predicates = copy.deepcopy(input_db)

    def get_next_rule(rules):
        """
        Retrieve rule in order considering dependency
        :param rules: A list of rule node object
        :return:
        """
        rule_map = {}
        idb_set = set()
        head_counter = collections.defaultdict(lambda: 0)

        for index, rule in enumerate(rules):
            node = RuleNode(rule[0], rule[1])
            idb_set.add(node.left)
            head_counter[node.left] += 1
            rule_map[str(index)] = node

        while rule_map:
            to_remove = set()
            for key in list(rule_map.keys()):
                node = rule_map[key]
                # loguru.logger.debug(node.right_set)
                if not idb_set.intersection(node.right_set):
                    yield node
                    head_counter[node.left] -= 1
                    if head_counter[node.left] == 0:
                        to_remove.add(node.left)
                    del rule_map[key]

            idb_set = idb_set.difference(to_remove)

    tuple2conf = {}

    def get_next_part_from_single_table(pred_name, num_splits=5):
        tuples = predicates[pred_name]
        sorted_tuples = sorted([(t, tuple2conf[t]) for t in tuples], key=lambda x: x[1])

        split_size = int(len(sorted_tuples) / num_splits)
        for x in range(0, len(sorted_tuples), split_size):
            yield list(map(lambda y: y[0], sorted_tuples[x:x + split_size])), \
                  float(
                      sum(map(lambda y: y[1], sorted_tuples[x:x + split_size])) / len(sorted_tuples[x:x + split_size]))

    def get_next_part_pair(pred1_name, pred2_name):
        for t1, avg1 in get_next_part_from_single_table(pred1_name):
            for t2, avg2 in get_next_part_from_single_table(pred2_name):
                yield t1 + t2, avg1 * avg2

    def store_intermediate_results(tuples, conf):
        """
        :param tuples: list of tuple string
        :param conf: confidence
        :return:
        """
        # TODO: add to in-memory map for predicates and confidence
        pass

    def initialize_tuple2conf():
        for _, items in input_db:
            for t in items:
                tuple2conf[t] = 1

    initialize_tuple2conf()
    for rule in get_next_rule(rules):
        # TODO: need to handle arity differently

        if len(rule.right_set) == 2:
            for data, conf in get_next_part_pair(rule.right_set[0], rule.right_set[1]):
                resulting_tuples = eval_datalog(data, rule)
                store_intermediate_results(resulting_tuples, conf * rule.conf)

        if len(rule.right_set) == 1:
            for t, avg in get_next_part_from_single_table(rule.right_set[0]):
                store_intermediate_results(t, avg*rule.conf)

        else:
            assert False

    return predicates, tuple2conf


def main():
    """
        Method for loading rule and load data into memory at once(cache)
    """

    rules, relations = rule_selector("<dbo:author>", 2)

    data = collections.defaultdict(set)

    for predicate in relations:
        sub, obj = "subject", "object"
        resp = pull_from_fuseki(sub, predicate, obj, 2)
        for s, o in extract_tuple_from_fuseki_response(resp):
            data[predicate].add((s, predicate, o))

    end_database, tuple_conf = eval_prob_query(rules, data)

    return end_database, tuple_conf


if __name__ == "__main__":
    # rules, relations = rule_selector("<dbo:author>", 1)
    # print(relations)
    # response = pull_from_fuseki('subject', '<dbo:creator>', 'object', 2)
    # pprint.pprint(response['results']['bindings'][0], indent=4)
    # pyDatalog.load(
    #     "+r('a','b')\na(N,M)<=r(M,N)"
    # )
    # print(pyDatalog.ask("a(X,Y)"))
    r = QUERY_PRED.match('abc(sdfsd)').group(1)
    print(r)
    #
    # pyDatalog.clear()
    # pyDatalog.load(
    #     "+r('Paul',e)\na(N,M)<=r(M,N)"
    # )
    # print(pyDatalog.ask("a(AC,B)"))
