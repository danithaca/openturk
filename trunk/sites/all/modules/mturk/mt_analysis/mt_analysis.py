# coding: utf8

'''
This file computes statistics and results for AMT tasks.
'''

from org.json.simple import JSONValue, JSONObject
from collections import defaultdict
from pprint import pprint
from fleiss import computeKappa
import xml.dom.minidom, sys, time, random, string, datetime
from mturk import MTurkComputeCommand
from org.drupal.project.async_command.AsyncCommand import Status

class ComputeAll(MTurkComputeCommand):

  def initialize(self):
    super(ComputeAll, self).initialize()
    # the main question used to compute fleiss and final results
    self.main_question = self.settings.get('main_question')

    # how much greater the majority results has to be in order to return a definite results
    self.majority_advantage = self.settings.get('analysis_results_majority_advantage')
    self.majority_advantage = int(self.majority_advantage) if self.majority_advantage != None else 1

    # if a HIT gets less than this minimum assignments, we'll just skip it.
    self.minimum_requirement = self.settings.get('analysis_results_minimum_requirement')
    self.minimum_requirement = int(self.minimum_requirement) if self.minimum_requirement != None else 0

    self.ignored_answers = self.settings.get('analysis_results_ignored_answers')
    self.ignored_answers = self.ignored_answers.split(',') if self.ignored_answers != None else []

    self.results = {}


  def execute(self):
    self.results['total_hits'] = self.db.queryValue("SELECT COUNT(hit_id) FROM {mt_task_hit} WHERE task_id=?", self.task_id)
    if self.results['total_hits'] == 0:
      return Status.FAILURE, 'Total HITs is 0, please load HITs first before computing results.', None


    row = self.db.query("SELECT MIN(h.max_assignments) m1, MAX(h.max_assignments) m2, SUM(h.max_assignments) m3\
      FROM {mt_task_hit} t INNER JOIN {mt_hit} h ON t.hit_id=h.hit_id WHERE task_id=?", self.task_id)
    row = row[0]
    m1, m2, m3 = row['m1'], row['m2'], row['m3']
    if m1 == m2:
      self.results['max_assignments'] = m1  # min and max is the same. otherwise 'max_assignments' is unset, and you can't compute fleiss.
    self.results['total_max_assignments'] = m3


    workers_set = set([])
    answers_summary = {}  # number of answers for each answer (needs to specify the 'main question' setting)
    assignments = self.db.query("SELECT t.hit_id, a.worker_id, a.assignment_status, a.answer_json\
        FROM {mt_task_hit} t INNER JOIN {mt_assignment} a ON t.hit_id=a.hit_id\
        WHERE task_id=?", self.task_id)
    if len(assignments) == 0:
      return Status.FAILURE, 'Total assignments is 0, please load assignments first before computing results.', None


    # hit_group[hit_id] = {worker_id: answer}
    hit_group = defaultdict(dict)  # group all assignments according to hit_id. if not assignments, then no hit_id as key.
    for row in assignments:
      hit_id, worker_id, assignment_status, answer_json = row['hit_id'], row['worker_id'], row['assignment_status'], row['answer_json']
      answer = self._get_answer(answer_json)
      hit_group[hit_id][worker_id] = answer
      workers_set.add(worker_id)
      answers_summary[answer] = answers_summary.get(answer, 0) + 1

      self.results['total_assignments'] = self.results.get('total_assignments', 0) + 1
      if assignment_status == 'Approved':
        self.results['total_assignments_approved'] = self.results.get('total_assignments_approved', 0) + 1
      elif assignment_status == 'Rejected':
        self.results['total_assignments_rejected'] = self.results.get('total_assignments_rejected', 0) + 1


    self.results['answers_summary'] = answers_summary
    self.results['total_workers'] = len(workers_set)


    hit_group_answers = defaultdict(dict)  # hit_group_answers[hit_id] = {answer: # of answers}
    hit_group_matrix = []  # this is a matrix with rows as hits, and columns as distinct answers, cell values as the number of HITs.
    all_answers = self.results['answers_summary'].keys()
    for hit_id, hit_assignments in hit_group.items():
      # hit_assignments => {worker_id: answer}
      answers = hit_assignments.values()
      answers_group = defaultdict(int)
      for a in answers:
        answers_group[a] += 1
      hit_group_answers[hit_id] = answers_group
      row = []
      for a in all_answers:
        row.append(answers_group[a])
      hit_group_matrix.append(row)
    #pprint(hit_group)
    #pprint(hit_group_answers)
    #pprint(hit_group_matrix)


    # calculate fleiss
    if 'max_assignments' in self.results:
      n = self.results['max_assignments']
      mat = [row for row in hit_group_matrix if sum(row) == n]
      self.results['fleiss_valid_hits'] = len(mat)
      if (self.results['fleiss_valid_hits'] > 0):
        self.results['fleiss'] = computeKappa(mat)
      else:
        self.results['fleiss'] = 'No finished HITs yet.'
    else:
      self.results['fleiss'] = 'All HITs needs to have the same maximum assignments in order to calculate Fleiss Kappa'
      self.results['fleiss_valid_hits'] = 0


    # calculate final results from noisy input
    self.results['results_majority'] = []
    rows = self.db.query("SELECT h.hit_id, h.annotation_id FROM {mt_hit} h INNER JOIN {mt_task_hit} t ON h.hit_id=t.hit_id WHERE t.task_id=?", self.task_id)
    for row in rows:
      hit_id, annotation_id = row['hit_id'], row['annotation_id']
      combined_answer = ','.join(hit_group[hit_id].values())
      answers_group = hit_group_answers[hit_id]

      # remove ignored answers
      for a in self.ignored_answers:
        if a in answers_group:
          del(answers_group[a])

      if sum(answers_group.values()) < self.minimum_requirement or sum(answers_group.values()) == 0:
        final_answer = None
      else:
        sorted_answers = answers_group.items() # flatten the dict into a list of tuples
        sorted_answers.sort(key=lambda r: r[1], reverse=True)
        diff = sorted_answers[0][1] - sorted_answers[1][1] if len(sorted_answers) > 1 else sorted_answers[0][1]
        if diff >= self.majority_advantage:
          final_answer = sorted_answers[0][0]
        else:
          final_answer = None
      self.results['results_majority'].append((hit_id, annotation_id, combined_answer, final_answer))

    self._save_results()
    #pprint(self.results)
    return Status.SUCCESS, 'successfully computed results.', None


  def _save_results(self):
    results_json = JSONValue.toJSONString(self.results)
    access_key = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(10))
    if self.db.queryValue("SELECT task_id FROM {mt_analysis} WHERE task_id=?", self.task_id) == None:
      self.db.update("INSERT INTO {mt_analysis}(task_id, results_json, access_key, updated) VALUE(?,?,?,?)",
        self.task_id, results_json, access_key, self.timestamp)
    else:
      self.db.update("UPDATE {mt_analysis} SET results_json=?, updated=? WHERE task_id=?",
        results_json, self.timestamp, self.task_id)


  def _get_answer(self, answer_json):
    o = JSONObject()
    answer_json = dict(o.getClass().cast(JSONValue.parse(answer_json)))
    if self.main_question != None and self.main_question in answer_json:
      # here we use the 'main question' setting.
      return answer_json[self.main_question]
    elif self.main_question == None and len(answer_json) > 0:
      # if main_question not set, use the first answer
      return answer_json.values()[0]
    return None

