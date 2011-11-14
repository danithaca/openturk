import sys
from mturk import MTurkServiceCommand
from org.drupal.project.async_command.AsyncCommand import Status

class GrantBonus(MTurkServiceCommand):

  def initialize(self):
    super(GrantBonus, self).initialize()
    self.bonus_id = self.record.getId1()

  def execute(self):
    row = self.db.query('SELECT worker_id, bonus_amount, assignment_id, message FROM {mt_bonus} WHERE bonus_id=?', self.bonus_id)[0]
    worker_id, bonus_amount, assignment_id, message = row['worker_id'], row['bonus_amount'], row['assignment_id'], row['message']
    bonus_amount = bonus_amount.doubleValue()  # original is BigDecimal.
    self.service.grantBonus(worker_id, bonus_amount, assignment_id, message)
    return Status.SUCCESS, 'Granted bonus: ' + str(bonus_amount) + ' to ' + worker_id
