# coding: utf8
# To compute leaderboard scores

from mturk import MTurkComputeCommand
from org.drupal.project.async_command.AsyncCommand import Status
import time 
from org.json.simple import JSONValue, JSONObject
from pprint import pprint

class ComputeKarma(MTurkComputeCommand):
  #Override
  def identifier(self):
    return 'ComputeKarma'
  
  def execute(self):
    results = {}
    #productivity = ProductivityLeaderboard(self)
    #results[productivity.identifier()] = productivity.computeRanks()
    responsiveness = ResponsivenessLeaderboard(self)
    results[responsiveness.identifier()] = responsiveness.computeRanks()
    return Status.SUCCESS, 'Successfully computed leaderboards.', results


# this is the Proxy design pattern, where the command is a field.
class BaseLeaderboard(object):

  def __init__(self, command):
    self.command = command
    self.db = command.db
    self.task_id = command.task_id
    self.settings = {}
    self.settings.update(command.settings)  # change java properties into Python dict
    self.processCommonSettings()
  
  def processCommonSettings(self):
    self.topN = int(self.settings.get('leaderboard_top_n', 10))
    self.disable = bool(self.settings.get(self.identifier() + '_disable', False))
    self.minimum = int(self.settings.get('leaderboard_minimum_requirement', 0))
    period = self.settings.get('leaderboard_valid_period', '').split('/')
    if (len(period) == 2):
      self.begin_timestamp = int(time.mktime(time.strptime(period[0], '%Y-%m-%d')))
      self.end_timestamp = int(time.mktime(time.strptime(period[1], '%Y-%m-%d')))
    else:
      self.begin_timestamp, self.end_timestamp = None, None
  
  def computeRanks(self):
    assert False, 'Please override'
    
  def computeBonus(self):
    key = self.identifier() + '_bonus_fixed'
    bonus_str = self.settings.get(key, '')
    if len(bonus_str) == 0:
      return []
    else:
      return map(float, bonus_str.split(','))
      
  def generateRows(self):
    ranks = self.computeRanks()
    bonuses = self.computeBonus()
    rows = []
    for position, record in enumerate(ranks):
      bonus = 0.0
      if (position < len(bonuses)):
        bonus = bonuses[position]
      rows.append({'name': record['name'], 'points': record['points'], 'bonus': bonus})
    return rows;
  
  def retrieveProductivityPoints(self, minimum=None, limit=None, begin=None, end=None, sort=False):
    sql = 'SELECT w.display_name AS name, COUNT(a.assignment_id) AS points FROM {mt_assignment} a INNER JOIN {mt_task_hit} h ON a.hit_id=h.hit_id \
      INNER JOIN {mt_worker} w ON w.worker_id=a.worker_id WHERE a.assignment_status="Approved" AND h.task_id = ' + str(self.task_id)
    if begin > 0:
      sql += ' AND a.submit_time >= ' + str(begin)
    if end > 0:
      sql += ' AND a.submit_time <= ' + str(end)
    sql += ' GROUP BY name'
    if minimum > 0:
      sql += ' HAVING points > ' + str(minimum)
    if sort == True:
      sql += ' ORDER BY points DESC'
    print self.db.d(sql)
    results = self.db.query(sql)
    if limit > 0:
      results = results[:limit]
    return results
  
  
class ProductivityLeaderboard(BaseLeaderboard):
  def identifier(self):
    return 'productivity'
    
  def computeRanks(self):
    return self.retrieveProductivityPoints(self.minimum, self.topN, self.begin_timestamp, self.end_timestamp, True)  


class ResponsivenessLeaderboard(BaseLeaderboard):
  def identifier(self):
    return 'responsiveness'
    
  def computeRanks(self):
    sql='''select w.display_name as name,
      (a.submit_time-h.hit_creation) as seconds from
      {mt_assignment} a inner join {mt_task_hit} t 
      on a.hit_id=t.hit_id inner join {mt_worker} w on
      w.worker_id=a.worker_id inner join {mt_hit} h on
      h.hit_id=a.hit_id where t.task_id = ? and
      a.assignment_status="Approved"'''
    if self.begin_timestamp > 0:
      sql += ' and a.submit_time >= %s'% str(self.begin_timestamp)
    if self.end_timestamp > 0:
      sql += ' and a.submit_time <= %s'% str(self.end_timestamp)
    sql += ' order by name, seconds asc'
    results = self.db.query(sql, self.task_id)
    pprint(results[0])
    data = {}
    for record in results:
      name = record['display_name']
      seconds = record['seconds']
      data.setdefault(name, []).append(seconds)
    median = []
    for key, items in data.items():
      length = len(items)
      if length > self.minimum:
        median.append((key, items[(length-1)/2]))
    sorted_median = sorted(median, key=lambda a:a[1])
    rows = []
    for name, value in sorted_median[:self.topN]:
      row = {}
      row['display_name'] = name
      minutes = int(round(value/60.0))
      row['points'] = str(minutes/60) + 'h' + str(minutes%60) + 'm'
      rows.append(row)
    return rows

class MTKarmaConformity(BaseLeaderboard):

  def __init__(self):
    super(MTKarmaConformity,self).__init__()
    self._neutral_answers = []
    self._points = []
    self._max_points = []

  def identifier():
    return 'conformity'

  def processGroup(self,group):
    answer_group = list_count_values(group)
    for name, answer in group.iteritems():
      self._points.setdefault(name, 0)
      self._max_points.setdefault(name, 0)
      self._max_points[name] += 2
      if answer_group[answer] == 1:
        self._points[name] -= 2
      elif answer_group[answer] > 1 and answer in self._neutral_answers:
        self._points[name] = 0
      elif answer_group[answer] > 1 and answer_group[answer] <= len(group.keys())/2:
        self._points[name] += 1
      elif answer_group[answer] > 1 and answer_group[answer] > len(group.keys())/2:
        self._points[name] += 2
      else: assert False

  def processHIT(self, hit_id):
    sql='''select w.display_name as name, a.answer_json 
      from {mt_assignment} a inner join {mt_worker} w on
      w.worker_id = a.worker_id where a.assignment = "Approved" and
      a.hit_id = %s'''%self.hit_id
    results = self.db.query(sql)
    group = {}
    main_question = self.settings.get('main_question',
        None)
    for record in results:
      name = record['name']
      #TODO: check the json file format to insure dict
      #answer_json = json.loads(record['answer_json'])

      # work-around for python json lib.
      answer_json_java = JSONObject(record['answer_json'])
      answer_json = {}
      for key in answer_json_java.keys():
        answer_json[key] = answer_json_java.get(key)

      if main_question and answer_json.get(main_question, None):
        group[name] = answer_json[main_question]
      elif not main_question and len(answer_json) > 0:
        values = [value for key,value in answer_json.items()]
        group[name] = values[0]
      if len(group) < 3:
        return False
      else:
        self.processGroup(group)
    def __handleRatioMode(self):
      ratio_mode = self.settings.get('conformit_ratio', False)
      if ratio_mode:
        for key, value in self.points.items():
          self.point[key] = round(value/self.max_points[key], 2)
    
    def handleLimitiToProductivity(self):
      limit_to_productivity = self.settings.get('conformity_limit_to_productivity', False)
      if limit_to_productivity:
        prod = ProductivityLeaderboard(self.task_id)
        productivity_rows = prod.generateRows()
        p_points = {}
        for p in productivity_rows:
          p_points[p['name']] = p['points']
        self.points = dict_intersect_key(self.points, p_points)

    def handleMinimumRequirementAndPeriod(self):
      if self.minimum > 0 or self.begin_timestamp > 0 or self.end_timestamp > 0:
        productivity_rows = self.retrieveProductivityPoints(self.minimum, None,
            self.begin_timestamp, self.end_timestamp, False)
        p_points= {}
        for p in productivity_rows:
          p_points = dict_intersect_key(self.points, p_points)

    def handleTopN(self):
      points_list = self.points.items()
      sorted_points = sorted(points_list, key=lambda a:a[1], reversed=True)
      return sorted_points[:self.topN]

    def computeRanks(self):
      if not (self.begin_timestemp > 0 or this.end_timetamp > 0):
        sql = '''select hit_id from {mt_task_hit} where task_id =
        %s'''%self.task_id
        hits = self.db.query(sql)
      else:
        sql = '''select distinct a.hit_id from {mt_task_hit} a inner
        join {mt_task_hit} h on a.hit_id=h.hit_id where
        a.ssignment_status = "Approved" and h.task_id = %s'''%self.task_id
        if self.begin_timestamp > 0:
          sql += ' and a.submit_time >= %s'%self.begin_timestamp
        if self.end_timestamp > 0:
          sql += ' and a.submit_time <= %s'%self.end_timestamp
        hits = self.db.query(sql)
      neutral_answers =\
      self.settings.get('conformity_neutral_answers','')
      if neutral_answers:
        self.neutral_answers = ','.split(neutral_answers)
        for hit in hits:
          self.processHIT(hit['hit_id'])
      self.handleMinimumRequirementAndPeriod();
      self.handleLimitToProductivity();
      self.handleRatioMode();
      self.handleTopN();
      ranks = []
      rank = {}
      for key, value in self.points.items():
        rank['name'] = key
        rank['points'] = value
        ranks.append(rank)
      return ranks



def dict_intersect_key(org_dict, trg_dict):
  return dict([(key, value) for key, value in org_dict if key in trg_dict.keys()])

def list_count_values(l):
  result = {}
  for item in l:
    if str(item) in result:
      result[str(item)] += 1
    else:
      result[str(item)] = 1
  return result


