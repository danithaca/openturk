# coding: utf8
# To compute leaderboard scores

from mturk import MTurkComputeCommand
from org.drupal.project.async_command.AsyncCommand import Status

class ComputeKarma(MTurkComputeCommand):
  #Override
  def identifier(self):
    return 'ComputeKarma'
  
  def execute(self):
    results = {}
    productivity = ProductivityLeaderboard(self)
    results[productivity.identifier()] = productivity.computeRanks()
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
      self.begin_timestamp = time.mktime(time.strptime(period[0], '%Y-%m-%d'))
      self.end_timestamp = time.mktime(time.strptime(period[1], '%Y-%m-%d'))
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
    pass

